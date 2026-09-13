"""Role-Based Access Control (RBAC) Dependency Module

Enforces role restrictions across mutating administrative and configuration endpoints
in accordance with AppUser roles ('ADMIN', 'SUPERVISOR', 'VIEWER').
"""

from typing import List, Optional
from fastapi import Header, HTTPException, status


def require_roles(allowed_roles: List[str]):
    """Returns a FastAPI dependency that verifies the requesting operator's role."""
    async def role_checker(
        x_user_role: Optional[str] = Header(
            None,
            description="Operator role for RBAC audit ('ADMIN', 'SUPERVISOR', 'VIEWER'). Defaults to SUPERVISOR for local development.",
        ),
        authorization: Optional[str] = Header(None, description="Bearer token header"),
    ) -> str:
        # Default role in local development/unauthenticated testing is SUPERVISOR
        current_role = "SUPERVISOR"

        if x_user_role:
            current_role = x_user_role.upper().strip()
        elif authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip().upper()
            if token in ("ADMIN", "SUPERVISOR", "VIEWER"):
                current_role = token

        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{current_role}' has insufficient privileges for this operation. Required: {allowed_roles}",
            )

        return current_role

    return role_checker

