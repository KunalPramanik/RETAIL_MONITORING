"""Authentication and User Management Router.

Provides secure OAuth2 password login, session profile, and password management endpoints.
Enforces:
- Direct authentication of Software Owner via PlatformSuperAdmin
- Fallback authentication of store users via AppUser
- Removal of any hardcoded credentials or bypasses
- Protection against public unauthorized user registration
- Secure password change endpoint for authenticated operators & Software Owner
- Brute-force rate limiting and generic error messages
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Any
import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from src.db.session import get_db, AsyncSessionLocal
from src.db.models import AppUser as User
from src.core.multi_tenant import PlatformAsyncSessionLocal
from src.db.platform_models import PlatformSuperAdmin, PlatformAuditLog
from src.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    record_failed_login,
    is_account_locked,
    reset_failed_logins,
    is_token_revoked,
    revoke_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from jose import jwt
from src.api.deps import get_current_user
from src.core.config import settings
from src.core.rate_limit import RateLimiter

logger = logging.getLogger("secops.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


class Token(BaseModel):
    access_token: str
    token_type: str
    role: Optional[str] = None
    isPlatformOwner: Optional[bool] = False
    refresh_token: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str
    role: Optional[str] = "VIEWER"


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str = Field(..., min_length=8)


@router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.auth_per_minute, seconds=60, scope="auth_login")),
):
    """Logs in an operator or Software Owner using either JSON body or OAuth2 form data."""
    content_type = request.headers.get("content-type", "").lower()
    raw_identifier = ""
    raw_password = ""

    if "application/json" in content_type:
        try:
            body = await request.json()
            raw_identifier = str(body.get("username") or body.get("email") or "").strip()
            raw_password = str(body.get("password") or "")
        except Exception:
            pass
    else:
        try:
            form = await request.form()
            raw_identifier = str(form.get("username") or "").strip()
            raw_password = str(form.get("password") or "")
        except Exception:
            pass

    if not raw_identifier or not raw_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    identifier = raw_identifier.strip()
    identifier_lower = identifier.lower()

    # Pre-flight Check: Login Lockout
    is_locked, rem_secs = is_account_locked(identifier)
    if is_locked:
        logger.warning("Authentication rejected: Account '%s' temporarily locked (%ds remaining)", identifier, rem_secs)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to excessive failed attempts. Please try again in {rem_secs} seconds.",
        )

    # 1. Primary Check: Software Owner in PlatformSuperAdmin
    async with PlatformAsyncSessionLocal() as p_session:
        p_res = await p_session.execute(
            select(PlatformSuperAdmin).where(
                or_(
                    PlatformSuperAdmin.email == identifier_lower,
                    PlatformSuperAdmin.username == identifier,
                    PlatformSuperAdmin.username == identifier_lower,
                )
            )
        )
        admin = p_res.scalar_one_or_none()
        if admin:
            if verify_password(raw_password, admin.password_hash):
                if not admin.is_active:
                    logger.warning("Software Owner account %s is deactivated", identifier)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account is deactivated. Access denied.",
                    )
                reset_failed_logins(identifier)
                admin.last_login_at = datetime.now(timezone.utc)
                await p_session.commit()
                access_token = create_access_token(
                    subject=admin.admin_id,
                    role="SUPER_ADMIN",
                    email=admin.email,
                    expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
                )
                refresh_token = create_refresh_token(
                    subject=admin.admin_id,
                    role="SUPER_ADMIN",
                    email=admin.email,
                )
                logger.info("Software Owner successfully authenticated: %s (role: SUPER_ADMIN)", admin.email)
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "role": "SUPER_ADMIN",
                    "isPlatformOwner": True,
                }
            else:
                attempts, is_now_locked = record_failed_login(identifier)
                lockout_sec = getattr(settings.security, "lockout_duration_seconds", 900)
                if is_now_locked:
                    logger.warning("Software Owner '%s' locked out after %d failed attempts", identifier, attempts)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Account temporarily locked due to excessive failed attempts ({attempts}). Locked for {lockout_sec} seconds.",
                    )
                logger.warning("Authentication failed for identifier: %s", identifier)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    # 2. Secondary Check: Store-level User in AppUser
    result = await db.execute(
        select(User).where(
            or_(
                User.email == identifier_lower,
                User.username == identifier,
            )
        )
    )
    user = result.scalars().first()
    if user and verify_password(raw_password, user.password_hash):
        if not getattr(user, "is_active", True):
            logger.warning("Authentication rejected: User account %s is deactivated", identifier)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user account. Access denied.",
            )

        reset_failed_logins(identifier)
        access_token = create_access_token(
            subject=user.user_id,
            role=user.role,
            email=user.email,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token = create_refresh_token(
            subject=user.user_id,
            role=user.role,
            email=user.email,
        )
        logger.info("Operator successfully authenticated: %s (role: %s)", identifier, user.role)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "role": user.role,
            "isPlatformOwner": False,
        }

    attempts, is_now_locked = record_failed_login(identifier)
    lockout_sec = getattr(settings.security, "lockout_duration_seconds", 900)
    if is_now_locked:
        logger.warning("Account '%s' locked out after %d failed attempts", identifier, attempts)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to excessive failed attempts ({attempts}). Locked for {lockout_sec} seconds.",
        )

    logger.warning("Authentication failed for identifier: %s", identifier)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    body: RefreshRequest,
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.auth_per_minute, seconds=60, scope="auth_refresh")),
):
    """Refreshes an expired access token using a valid refresh token with automatic token rotation."""
    raw_token = body.refresh_token.strip()
    if not raw_token or is_token_revoked(raw_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token. Please log in again.",
        )
    try:
        payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    if payload.get("token_use") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provided token is not a refresh token.",
        )

    # Invalidate the consumed refresh token (token rotation)
    revoke_token(raw_token)

    subject = payload.get("sub")
    role = payload.get("role")
    email = payload.get("email")

    new_access_token = create_access_token(
        subject=subject,
        role=role,
        email=email,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh_token = create_refresh_token(
        subject=subject,
        role=role,
        email=email,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "role": role,
        "isPlatformOwner": role == "SUPER_ADMIN",
    }


@router.post("/logout")
async def logout_user(
    request: Request,
    current_user: Any = Depends(get_current_user),
):
    """Logs out the active operator and records an audit log entry."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        from src.security import revoke_token
        revoke_token(token)
    logger.info("Operator logged out: %s (id: %s, role: %s)", current_user.email, current_user.user_id, current_user.role)
    return {"msg": "Successfully logged out", "status": "LOGGED_OUT"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.auth_per_minute, seconds=60, scope="auth_register")),
):
    """Registers a new user account, populating both canonical email and display username."""
    raw_identifier = (user_in.email or user_in.username or "").strip()
    if not raw_identifier:
        raise HTTPException(status_code=400, detail="Username or email must be provided")

    # Reconcile email vs username handle
    if "@" in raw_identifier:
        resolved_email = raw_identifier
        resolved_username = user_in.username.strip() if user_in.username else raw_identifier.split("@")[0]
    else:
        resolved_username = raw_identifier
        resolved_email = user_in.email.strip() if user_in.email else f"{raw_identifier}@secops.local"

    # Ensure uniqueness across both fields
    existing = await db.execute(
        select(User).where(
            or_(
                User.email == resolved_email,
                User.username == resolved_username,
            )
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="User already registered with this email or username")
        
    hashed_password = get_password_hash(user_in.password)
    assigned_role = user_in.role.upper() if user_in.role else "VIEWER"
    if assigned_role not in ("ADMIN", "SUPERVISOR", "VIEWER"):
        assigned_role = "VIEWER"

    db_user = User(
        user_id=str(uuid.uuid4()),
        email=resolved_email,
        username=resolved_username,
        password_hash=hashed_password,
        role=assigned_role,
        is_active=True,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return {
        "msg": "User created successfully",
        "user_id": db_user.user_id,
        "email": db_user.email,
        "username": db_user.username,
        "role": db_user.role,
    }


@router.get("/me")
async def read_users_me(current_user: Any = Depends(get_current_user)):
    """Returns the authenticated operator or Software Owner profile."""
    role = (current_user.role or "VIEWER").upper()
    owner_email = (os.getenv("BOOTSTRAP_OWNER_EMAIL") or "").strip().lower()
    is_owner = role == "SUPER_ADMIN" or (bool(owner_email) and (current_user.email or "").strip().lower() == owner_email)

    return {
        "id": current_user.user_id,
        "user_id": current_user.user_id,
        "email": current_user.email,
        "username": current_user.username or current_user.email,
        "role": "SUPER_ADMIN" if is_owner else role,
        "isPlatformOwner": is_owner,
    }


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Secure password change for the currently authenticated Software Owner or operator."""
    role = (current_user.role or "").upper()
    
    # Check if current user is Software Owner in PlatformSuperAdmin
    if role == "SUPER_ADMIN":
        async with PlatformAsyncSessionLocal() as p_session:
            admin = await p_session.get(PlatformSuperAdmin, current_user.user_id)
            if not admin:
                stmt = select(PlatformSuperAdmin).where(PlatformSuperAdmin.email == current_user.email.lower())
                res = await p_session.execute(stmt)
                admin = res.scalar_one_or_none()

            if not admin or not verify_password(req.currentPassword, admin.password_hash):
                raise HTTPException(status_code=400, detail="Current password verification failed.")

            admin.password_hash = get_password_hash(req.newPassword)
            audit = PlatformAuditLog(
                actor_id=admin.admin_id,
                actor_type="SUPER_ADMIN",
                action="CHANGE_PASSWORD",
                details={"email": admin.email, "status": "SUCCESS"},
            )
            p_session.add(audit)
            await p_session.commit()
            logger.info("Software Owner %s successfully changed password.", admin.email)
            return {"status": "SUCCESS", "message": "Software Owner password updated successfully."}

    # Store-level user
    user = await db.get(User, current_user.user_id)
    if not user or not verify_password(req.currentPassword, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password verification failed.")

    user.password_hash = get_password_hash(req.newPassword)
    await db.commit()
    logger.info("User %s successfully changed password.", user.email)
    return {"status": "SUCCESS", "message": "Password updated successfully."}
