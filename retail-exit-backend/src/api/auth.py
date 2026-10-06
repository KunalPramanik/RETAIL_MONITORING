"""Authentication and User Management Router

Provides secure OAuth2 password login, user registration, and profile endpoints.
Supports unified authentication by either email address or username handle.
"""

from datetime import timedelta
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel, Field

from src.db.session import get_db
from src.db.models import AppUser as User
from src.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from src.api.deps import get_current_user
from src.core.config import settings
from src.core.rate_limit import RateLimiter

router = APIRouter(prefix="/auth", tags=["auth"])

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str = Field(..., min_length=4)
    role: str = "VIEWER"

@router.post("/login", response_model=Token)
async def login_for_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    _rate_limit: bool = Depends(RateLimiter(times=settings.rate_limit.auth_per_minute, seconds=60, scope="auth_login")),
):
    """Logs in an operator using either their registered email address or username handle."""
    identifier = form_data.username.strip()
    result = await db.execute(
        select(User).where(
            or_(
                User.email == identifier,
                User.username == identifier,
            )
        )
    )
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.user_id, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

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
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated operator profile."""
    return {
        "id": current_user.user_id,
        "user_id": current_user.user_id,
        "email": current_user.email,
        "username": current_user.username or current_user.email,
        "role": current_user.role,
    }
