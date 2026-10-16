from typing import Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import AppUser as User
from src.security import SECRET_KEY, ALGORITHM

from src.core.multi_tenant import PlatformAsyncSessionLocal
from src.db.platform_models import PlatformSuperAdmin

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)) -> Any:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role", "")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 1. Check PlatformSuperAdmin if role claim or subject points to platform admin
    if role == "SUPER_ADMIN" or "admin_" in user_id or "usr_owner_" in user_id:
        async with PlatformAsyncSessionLocal() as p_session:
            admin = await p_session.get(PlatformSuperAdmin, user_id)
            if not admin:
                stmt = select(PlatformSuperAdmin).where(
                    PlatformSuperAdmin.email == payload.get("email", "").lower()
                )
                res = await p_session.execute(stmt)
                admin = res.scalar_one_or_none()
            if admin:
                if not getattr(admin, "is_active", True):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Platform administrator account is suspended or deactivated.",
                    )
                return admin

    # 2. Check AppUser in store database
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalars().first()
    if user:
        if not getattr(user, "is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended or deactivated. Automatic session termination enforced.",
            )
        if getattr(user, "store_id", None):
            async with PlatformAsyncSessionLocal() as p_session:
                from src.db.platform_models import PlatformTenant
                tenant = await p_session.get(PlatformTenant, user.store_id)
                if tenant and tenant.status == "SUSPENDED":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Company store subscription has been suspended by platform administrator.",
                    )
        return user

    # 3. Fallback check in PlatformSuperAdmin
    async with PlatformAsyncSessionLocal() as p_session:
        admin = await p_session.get(PlatformSuperAdmin, user_id)
        if admin:
            if not getattr(admin, "is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Platform administrator account is suspended or deactivated.",
                )
            return admin

    raise credentials_exception

def role_required(required_roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_checker
