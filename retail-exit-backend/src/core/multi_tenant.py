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
from sqlalchemy import select

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
    f"sqlite+aiosqlite:///{PLATFORM_DB_PATH}"
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

    # Bootstrap master super admin if none exists
    async with PlatformAsyncSessionLocal() as session:
        res = await session.execute(select(PlatformSuperAdmin).limit(1))
        existing_admin = res.scalar_one_or_none()
        if not existing_admin:
            initial_user = os.getenv("PLATFORM_SUPER_ADMIN_USER", "masteradmin")
            initial_email = os.getenv("PLATFORM_SUPER_ADMIN_EMAIL", "master@secops.platform")
            initial_pass = os.getenv("PLATFORM_SUPER_ADMIN_PASSWORD", "SecOps#Platform2026!Master")
            super_admin = PlatformSuperAdmin(
                username=initial_user,
                email=initial_email,
                password_hash=get_password_hash(initial_pass),
                role="SUPER_ADMIN",
                is_active=True,
            )
            session.add(super_admin)
            await session.commit()
            logger.info("Master Super Admin account bootstrapped (%s).", initial_user)


def sanitize_slug(name: str) -> str:
    """Creates a clean, URL-safe tenant slug from company name."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower())
    return s.strip("-") or f"tenant-{uuid.uuid4().hex[:6]}"


def get_tenant_db_url(tenant_id: str, slug: str) -> str:
    """Derives isolated database connection URL for a specific tenant."""
    base_url = settings.DATABASE_URL.strip()
    if base_url.startswith("sqlite"):
        tenants_dir = os.path.join(os.getcwd(), "data", "tenants")
        os.makedirs(tenants_dir, exist_ok=True)
        tenant_db_file = os.path.join(tenants_dir, f"{slug}_{tenant_id[:8]}.db")
        return f"sqlite+aiosqlite:///{tenant_db_file}"
    elif "postgresql" in base_url:
        # For Postgres, parse URL and append dedicated tenant database name
        # e.g., postgresql+asyncpg://user:pass@host:5432/secops_tenant_<slug>
        prefix, _, db_part = base_url.rpartition("/")
        clean_db_name = f"secops_tenant_{slug.replace('-', '_')}_{tenant_id[:8]}"
        return f"{prefix}/{clean_db_name}"
    else:
        # Default fallback to file-based isolation
        tenants_dir = os.path.join(os.getcwd(), "data", "tenants")
        os.makedirs(tenants_dir, exist_ok=True)
        return f"sqlite+aiosqlite:///{tenants_dir}/{tenant_id}.db"


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
