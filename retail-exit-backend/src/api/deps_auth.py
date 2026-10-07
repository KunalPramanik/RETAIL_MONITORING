"""Role-Based Access Control (RBAC) Dependency Module

Enforces cryptographic JWT signature verification and role-based restrictions
across mutating administrative and configuration endpoints in accordance with
AppUser roles ('SUPER_ADMIN', 'ADMIN', 'SUPERVISOR', 'VIEWER').
"""

from typing import List, Optional
import logging
from fastapi import Header, HTTPException, status, Depends
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.session import get_db
from src.db.models import AppUser

logger = logging.getLogger("secops.auth")


def require_roles(allowed_roles: List[str]):
    """Returns a FastAPI dependency that cryptographically verifies the bearer token and checks RBAC permissions."""
    async def role_checker(
        authorization: Optional[str] = Header(None, description="Bearer token header"),
        db: AsyncSession = Depends(get_db),
    ) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided. Bearer token required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization[7:].strip()
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            user_id: Optional[str] = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload: missing subject identifier.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except JWTError as err:
            logger.warning("Cryptographic JWT signature verification failed: %s", err)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, expired, or forged authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Derive role from verified database record to ensure revoked/deactivated accounts are immediately rejected
        current_role = None
        try:
            result = await db.execute(select(AppUser).where(AppUser.user_id == user_id))
            user = result.scalars().first()
            if user:
                if not getattr(user, "is_active", True):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User account is deactivated. Access revoked.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                current_role = (user.role or "VIEWER").upper().strip()
        except HTTPException:
            raise
        except Exception as db_err:
            logger.debug("Database user lookup fallback to signed token claims: %s", db_err)

        # Fallback to cryptographically signed role claim in token payload if DB lookup is unavailable
        if not current_role:
            current_role = (payload.get("role") or "VIEWER").upper().strip()

        normalized_allowed = [r.upper().strip() for r in allowed_roles]
        # SUPER_ADMIN retains full privilege across all role tiers
        if current_role != "SUPER_ADMIN" and current_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{current_role}' has insufficient privileges for this operation. Required: {allowed_roles}",
            )

        return current_role

    return role_checker
