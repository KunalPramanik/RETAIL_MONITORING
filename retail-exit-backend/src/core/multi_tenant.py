"""Multi-Tenant Isolation & Database Provisioning Engine.

Implements Section 3 of the V8 Master Prompt:
- Platform control-plane database isolation
- Isolated database-per-tenant operational storage
- Tenant lifecycle provisioning, rollback, and verification
- Dynamic, cached tenant database session routing
"""

import os
import re
import uuid
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.pool import NullPool
from sqlalchemy import select, or_

from src.core.config import settings
from src.db.platform_models import PlatformBase, PlatformTenant, PlatformSuperAdmin, PlatformAuditLog
from src.db.models.base import Base
from src.db.models.store import Store, ThresholdConfig
from src.db.models.alert import AppUser
from src.security import get_password_hash

logger = logging.getLogger("secops.multi_tenant")

# Platform control-plane database path
PLATFORM_DB_DIR = os.path.join(os.getcwd(), "data", "platform")
os.makedirs(PLATFORM_DB_DIR, exist_ok=True)
PLATFORM_DB_PATH = os.path.join(PLATFORM_DB_DIR, "control_plane.db")
PLATFORM_DATABASE_URL = os.getenv(
    "PLATFORM_DATABASE_URL",
    settings.DATABASE_URL if "postgresql" in settings.DATABASE_URL else f"sqlite+aiosqlite:///{PLATFORM_DB_PATH}"
)

# Engine & Session factory for platform control plane
platform_engine: AsyncEngine = create_async_engine(
    PLATFORM_DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)
PlatformAsyncSessionLocal = async_sessionmaker(
    bind=platform_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Cache for tenant database engines to prevent per-query overhead
_tenant_engines: Dict[str, AsyncEngine] = {}
_tenant_session_makers: Dict[str, async_sessionmaker[AsyncSession]] = {}


async def init_platform_db() -> None:
    """Initializes platform control-plane database schema and default super admin if missing."""
    async with platform_engine.begin() as conn:
        await conn.run_sync(PlatformBase.metadata.create_all)
    logger.info("Platform control-plane schema verified.")

    # Bootstrap master super admin: Software Owner
    env = os.getenv("ENVIRONMENT", "production").lower()
    owner_email = os.getenv("BOOTSTRAP_OWNER_EMAIL", "").strip().lower()
    owner_password = os.getenv("BOOTSTRAP_OWNER_PASSWORD", "")

    if not owner_email:
        if env in ("development", "test", "testing"):
            owner_email = "ces@gmail.com"
        else:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: BOOTSTRAP_OWNER_EMAIL must be explicitly provided in production."
            )

    if not owner_password:
        if env in ("development", "test", "testing"):
            owner_password = "Ces@1234"
        else:
            import secrets
            owner_password = secrets.token_urlsafe(24)
            logger.critical("=" * 60)
            logger.critical("BOOTSTRAP SUPER ADMIN CREATED")
            logger.critical("Email: %s", owner_email)
            logger.critical("Generated Password: %s", owner_password)
            logger.critical("Save this credential immediately. It will not be shown again.")
            logger.critical("=" * 60)
    elif env == "production" and owner_password in ("Ces@1234", "admin123", "password", "changeme", "12345678"):
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Weak/default BOOTSTRAP_OWNER_PASSWORD is strictly prohibited in production."
        )

    owner_username = owner_email.split("@")[0]

    async with PlatformAsyncSessionLocal() as session:
        ces_res = await session.execute(
            select(PlatformSuperAdmin).where(
                or_(
                    PlatformSuperAdmin.email == owner_email,
                    PlatformSuperAdmin.username == owner_email,
                    PlatformSuperAdmin.username == owner_username,
                )
            )
        )
        ces_super = ces_res.scalar_one_or_none()
        if not ces_super:
            ces_super_admin = PlatformSuperAdmin(
                username=owner_username,
                email=owner_email,
                password_hash=get_password_hash(owner_password),
                role="SUPER_ADMIN",
                is_active=True,
            )
            session.add(ces_super_admin)
            await session.commit()
            logger.info("Software Owner account (%s) successfully bootstrapped into PlatformSuperAdmin.", owner_email)
        else:
            # Idempotent: preserve existing password and account state
            if not ces_super.is_active:
                ces_super.is_active = True
                await session.commit()
                logger.info("Software Owner account (%s) reactivated without modifying credentials.", owner_email)


def sanitize_slug(name: str) -> str:
    """Creates a clean, URL-safe tenant slug from company name."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower())
    return s.strip("-") or f"tenant-{uuid.uuid4().hex[:6]}"


def get_tenant_db_url(tenant_id: str, slug: str) -> str:
    """Derives isolated database connection URL for a specific tenant."""
    base_url = settings.DATABASE_URL.strip()
    tenant_mode = os.getenv("TENANT_DB_MODE", "sqlite").lower()
    if tenant_mode == "postgres" and "postgresql" in base_url:
        prefix, _, db_part = base_url.rpartition("/")
        clean_db_name = f"secops_tenant_{slug.replace('-', '_')}_{tenant_id[:8]}"
        return f"{prefix}/{clean_db_name}"
    else:
        # Default robust physical isolation: dedicated database file per tenant
        tenants_dir = os.path.join(os.getcwd(), "data", "tenants")
        os.makedirs(tenants_dir, exist_ok=True)
        tenant_db_file = os.path.join(tenants_dir, f"{slug}_{tenant_id[:8]}.db")
        return f"sqlite+aiosqlite:///{tenant_db_file}"


def get_tenant_session_maker(db_url: str) -> async_sessionmaker[AsyncSession]:
    """Retrieves or instantiates cached async session maker for a tenant database."""
    if db_url not in _tenant_session_makers:
        engine = create_async_engine(
            db_url,
            echo=False,
            future=True,
            poolclass=NullPool,
        )
        _tenant_engines[db_url] = engine
        _tenant_session_makers[db_url] = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _tenant_session_makers[db_url]


class TenantProvisioningService:
    """Orchestrates atomic company creation, separate DB provisioning, and role initialization."""

    @classmethod
    async def provision_tenant(
        cls,
        company_name: str,
        admin_email: str,
        admin_password: str,
        admin_name: str = "Company Admin",
        timezone_str: str = "Asia/Kolkata",
        actor_id: str = "SYSTEM",
    ) -> Dict[str, Any]:
        """Creates a new company with an isolated operational database.
        
        Strictly enforces 0 mock operational data upon initial creation.
        """
        async with PlatformAsyncSessionLocal() as plat_session:
            # 1. Verify company name uniqueness in registry
            check = await plat_session.execute(
                select(PlatformTenant).where(PlatformTenant.name == company_name.strip())
            )
            if check.scalar_one_or_none():
                raise ValueError(f"Company name '{company_name}' is already registered.")

            tenant_id = str(uuid.uuid4())
            slug = sanitize_slug(company_name)

            # Ensure slug uniqueness
            slug_check = await plat_session.execute(
                select(PlatformTenant).where(PlatformTenant.slug == slug)
            )
            if slug_check.scalar_one_or_none():
                slug = f"{slug}-{uuid.uuid4().hex[:4]}"

            db_url = get_tenant_db_url(tenant_id, slug)

            # Register tenant in PROVISIONING state
            tenant = PlatformTenant(
                tenant_id=tenant_id,
                name=company_name.strip(),
                slug=slug,
                db_identifier=db_url,
                status="PROVISIONING",
                timezone=timezone_str,
                contact_email=admin_email.strip(),
            )
            plat_session.add(tenant)
            await plat_session.commit()

        # 2. Initialize isolated tenant database schema
        tenant_engine = None
        try:
            session_maker = get_tenant_session_maker(db_url)
            tenant_engine = _tenant_engines[db_url]

            # Execute schema migrations / DDL on tenant database
            async with tenant_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # 3. Initialize baseline Store & provision Initial Company Admin
            async with session_maker() as t_session:
                store_id = f"store_{uuid.uuid4().hex[:8]}"
                store = Store(
                    store_id=store_id,
                    name=f"{company_name} Main Facility",
                    timezone=timezone_str,
                )
                t_session.add(store)

                thresh = ThresholdConfig(
                    config_id=f"cfg_{uuid.uuid4().hex[:8]}",
                    store_id=store_id,
                    unit_tolerance=0,
                    camera_offline_alert_after_sec=60,
                )
                t_session.add(thresh)

                # Provision Initial Tenant Administrator
                admin_user = AppUser(
                    user_id=str(uuid.uuid4()),
                    email=admin_email.strip().lower(),
                    username=admin_email.strip().lower().split("@")[0],
                    password_hash=get_password_hash(admin_password),
                    role="ADMIN",
                    store_id=store_id,
                    is_active=True,
                )
                t_session.add(admin_user)
                await t_session.commit()

            # 4. Mark tenant ACTIVE and record platform audit log
            async with PlatformAsyncSessionLocal() as plat_session:
                t_record = await plat_session.get(PlatformTenant, tenant_id)
                if t_record:
                    t_record.status = "ACTIVE"

                audit = PlatformAuditLog(
                    actor_id=actor_id,
                    actor_type="SUPER_ADMIN",
                    action="PROVISION_TENANT",
                    tenant_id=tenant_id,
                    details={
                        "company_name": company_name,
                        "slug": slug,
                        "admin_email": admin_email,
                        "db_identifier": db_url,
                    },
                )
                plat_session.add(audit)
                await plat_session.commit()

            logger.info("Tenant '%s' (%s) successfully provisioned with isolated database.", company_name, tenant_id)
            return {
                "tenantId": tenant_id,
                "name": company_name,
                "slug": slug,
                "status": "ACTIVE",
                "adminEmail": admin_email,
                "timezone": timezone_str,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.error("Tenant provisioning failed for '%s': %s", company_name, exc)
            # Rollback: mark tenant DECOMMISSIONED in control plane
            async with PlatformAsyncSessionLocal() as plat_session:
                t_record = await plat_session.get(PlatformTenant, tenant_id)
                if t_record:
                    t_record.status = "DECOMMISSIONED"
                await plat_session.commit()
            raise RuntimeError(f"Tenant provisioning failed: {exc}") from exc


@asynccontextmanager
async def get_tenant_db(tenant_id: Optional[str] = None) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding isolated database session for requested tenant."""
    if not tenant_id:
        # Fall back to default primary database session
        from src.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return

    # Look up tenant in platform registry
    async with PlatformAsyncSessionLocal() as plat_session:
        tenant_res = await plat_session.execute(
            select(PlatformTenant).where(
                (PlatformTenant.tenant_id == tenant_id) | (PlatformTenant.slug == tenant_id)
            )
        )
        tenant = tenant_res.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found in platform registry.")
        if tenant.status != "ACTIVE":
            raise PermissionError(f"Tenant '{tenant.name}' is {tenant.status}.")
        db_url = tenant.db_identifier

    session_maker = get_tenant_session_maker(db_url)
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
