"""Platform Control-Plane Administration API Endpoints.

Implements Master Super Admin management and Company Provisioning.
Enforces Section 3 of the V8 Master Prompt.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy import select, desc
from datetime import datetime, timezone

from src.core.multi_tenant import (
    PlatformAsyncSessionLocal,
    TenantProvisioningService,
    get_tenant_session_maker,
    init_platform_db,
)
from src.db.platform_models import PlatformTenant, PlatformSuperAdmin, PlatformAuditLog
from src.db.models.alert import AppUser
from src.security import verify_password, get_password_hash, create_access_token
from jose import jwt, JWTError
from src.core.config import settings

router = APIRouter(prefix="/platform", tags=["Platform Control Plane"])


# --- Schemas ---

class PlatformLoginRequest(BaseModel):
    usernameOrEmail: str
    password: str


class PlatformLoginResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    adminId: str
    username: str
    email: str
    role: str


class TenantProvisionRequest(BaseModel):
    companyName: str = Field(..., min_length=2, max_length=255)
    adminEmail: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    adminPassword: str = Field(..., min_length=8)
    adminName: Optional[str] = "Company Admin"
    timezone: Optional[str] = "Asia/Kolkata"


class TenantResponse(BaseModel):
    tenantId: str
    name: str
    slug: str
    dbIdentifier: str
    status: str
    timezone: str
    currency: str
    contactEmail: Optional[str] = None
    createdAt: str
    updatedAt: str


class TenantStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|SUSPENDED|DECOMMISSIONED)$")
    reason: Optional[str] = None


class TenantUserProvisionRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    username: Optional[str] = None
    password: str = Field(..., min_length=8)
    role: str = Field(..., pattern="^(ADMIN|SUPERVISOR|VIEWER)$")


# --- Auth Dependency for Master Super Admin ---

async def require_master_super_admin(
    authorization: Optional[str] = Header(None, description="Bearer token header"),
) -> PlatformSuperAdmin:
    """Verifies that the caller has authenticated as a Platform Master Super Admin."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Master Super Admin authentication credentials required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:].strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        admin_id: Optional[str] = payload.get("sub")
        role: Optional[str] = payload.get("role")
        if not admin_id or role != "SUPER_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Master Super Admin privileges required.",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with PlatformAsyncSessionLocal() as session:
        admin = await session.get(PlatformSuperAdmin, admin_id)
        if not admin or not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Master Super Admin account is inactive or revoked.",
            )
        return admin


# --- Endpoints ---

@router.post("/auth/login", response_model=PlatformLoginResponse)
async def platform_login(req: PlatformLoginRequest):
    """Authenticates Master Super Admin into the platform control plane."""
    # Ensure platform schema & initial admin exists
    await init_platform_db()

    async with PlatformAsyncSessionLocal() as session:
        ident = req.usernameOrEmail.strip()
        stmt = select(PlatformSuperAdmin).where(
            (PlatformSuperAdmin.username == ident) | (PlatformSuperAdmin.email == ident)
        )
        res = await session.execute(stmt)
        admin = res.scalar_one_or_none()

        if not admin or not verify_password(req.password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Master Super Admin credentials.",
            )

        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )

        admin.last_login_at = datetime.now(timezone.utc)
        await session.commit()

        token = create_access_token(subject=admin.admin_id, role="SUPER_ADMIN")
        return PlatformLoginResponse(
            accessToken=token,
            adminId=admin.admin_id,
            username=admin.username,
            email=admin.email,
            role=admin.role,
        )


@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    admin: PlatformSuperAdmin = Depends(require_master_super_admin),
):
    """Lists all registered company tenants across the platform."""
    async with PlatformAsyncSessionLocal() as session:
        res = await session.execute(select(PlatformTenant).order_by(desc(PlatformTenant.created_at)))
        tenants = res.scalars().all()
        return [
            TenantResponse(
                tenantId=t.tenant_id,
                name=t.name,
                slug=t.slug,
                dbIdentifier=t.db_identifier,
                status=t.status,
                timezone=t.timezone,
                currency=t.currency,
                contactEmail=t.contact_email,
                createdAt=t.created_at.isoformat() if t.created_at else "",
                updatedAt=t.updated_at.isoformat() if t.updated_at else "",
            )
            for t in tenants
        ]


@router.post("/tenants", response_model=Dict[str, Any], status_code=201)
async def create_tenant(
    req: TenantProvisionRequest,
    admin: PlatformSuperAdmin = Depends(require_master_super_admin),
):
    """Provisions a new company with an isolated operational database."""
    try:
        result = await TenantProvisioningService.provision_tenant(
            company_name=req.companyName,
            admin_email=req.adminEmail,
            admin_password=req.adminPassword,
            admin_name=req.adminName or "Company Admin",
            timezone_str=req.timezone or "Asia/Kolkata",
            actor_id=admin.admin_id,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Provisioning failed: {exc}")


@router.patch("/tenants/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: str,
    req: TenantStatusUpdateRequest,
    admin: PlatformSuperAdmin = Depends(require_master_super_admin),
):
    """Activates, suspends, or decommissions a company tenant."""
    async with PlatformAsyncSessionLocal() as session:
        tenant = await session.get(PlatformTenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found.")

        old_status = tenant.status
        tenant.status = req.status
        tenant.updated_at = datetime.now(timezone.utc)

        audit = PlatformAuditLog(
            actor_id=admin.admin_id,
            actor_type="SUPER_ADMIN",
            action="UPDATE_TENANT_STATUS",
            tenant_id=tenant_id,
            details={"old_status": old_status, "new_status": req.status, "reason": req.reason},
        )
        session.add(audit)
        await session.commit()
        return {"tenantId": tenant_id, "status": tenant.status, "previousStatus": old_status}


@router.post("/tenants/{tenant_id}/users", status_code=201)
async def provision_tenant_user(
    tenant_id: str,
    req: TenantUserProvisionRequest,
    admin: PlatformSuperAdmin = Depends(require_master_super_admin),
):
    """Allows Master Super Admin to provision an ADMIN or SUPERVISOR user into a tenant's database."""
    async with PlatformAsyncSessionLocal() as session:
        tenant = await session.get(PlatformTenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found.")
        if tenant.status != "ACTIVE":
            raise HTTPException(status_code=400, detail=f"Cannot provision user for tenant in {tenant.status} status.")
        db_url = tenant.db_identifier

    # Access tenant's isolated database
    session_maker = get_tenant_session_maker(db_url)
    async with session_maker() as t_session:
        # Check email uniqueness in tenant DB
        exists = await t_session.execute(
            select(AppUser).where(AppUser.email == req.email.strip().lower())
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"User with email '{req.email}' already exists in tenant.")

        username = req.username or req.email.split("@")[0]
        new_user = AppUser(
            email=req.email.strip().lower(),
            username=username.strip(),
            password_hash=get_password_hash(req.password),
            role=req.role,
            is_active=True,
        )
        t_session.add(new_user)
        await t_session.commit()

    # Log in platform audit trail
    async with PlatformAsyncSessionLocal() as session:
        audit = PlatformAuditLog(
            actor_id=admin.admin_id,
            actor_type="SUPER_ADMIN",
            action="PROVISION_TENANT_USER",
            tenant_id=tenant_id,
            details={"user_email": req.email, "role": req.role, "username": username},
        )
        session.add(audit)
        await session.commit()

    return {"userId": new_user.user_id, "email": new_user.email, "role": new_user.role, "tenantId": tenant_id}


@router.get("/audit-logs")
async def list_platform_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    admin: PlatformSuperAdmin = Depends(require_master_super_admin),
):
    """Retrieves platform-level audit logs."""
    async with PlatformAsyncSessionLocal() as session:
        res = await session.execute(
            select(PlatformAuditLog).order_by(desc(PlatformAuditLog.created_at)).limit(limit)
        )
        logs = res.scalars().all()
        return [
            {
                "logId": l.log_id,
                "actorId": l.actor_id,
                "actorType": l.actor_type,
                "action": l.action,
                "tenantId": l.tenant_id,
                "details": l.details,
                "createdAt": l.created_at.isoformat() if l.created_at else "",
            }
            for l in logs
        ]
