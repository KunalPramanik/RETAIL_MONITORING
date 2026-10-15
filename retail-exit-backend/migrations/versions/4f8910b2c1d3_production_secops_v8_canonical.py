"""SEC-OPS V8 Canonical Production Migration

Revision ID: 4f8910b2c1d3
Revises: 3a419bf4a775
Create Date: 2026-10-15 19:49:00.000000

Non-destructive upgrade ensuring platform control-plane and store operational tables,
constraints, and indexes exist without dropping historical business data.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '4f8910b2c1d3'
down_revision: Union[str, Sequence[str], None] = '3a419bf4a775'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Platform Control-Plane Tables (Non-Destructive)
    conn = op.get_bind()
    
    # platform_tenant
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.platform_tenant (
        tenant_id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(255) UNIQUE NOT NULL,
        slug VARCHAR(64) UNIQUE NOT NULL,
        db_identifier VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'PROVISIONING',
        timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
        currency VARCHAR(16) NOT NULL DEFAULT 'INR',
        contact_email VARCHAR(255),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # platform_super_admin
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.platform_super_admin (
        admin_id VARCHAR(36) PRIMARY KEY,
        username VARCHAR(64) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(32) NOT NULL DEFAULT 'SUPER_ADMIN',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_login_at TIMESTAMPTZ
    );
    """)

    # platform_subscription_tier
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.platform_subscription_tier (
        tier_id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(64) UNIQUE NOT NULL,
        max_cameras INTEGER NOT NULL DEFAULT 4,
        price_cents INTEGER NOT NULL DEFAULT 0,
        currency VARCHAR(16) NOT NULL DEFAULT 'INR',
        billing_cycle VARCHAR(16) NOT NULL DEFAULT 'MONTHLY',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # platform_store_subscription
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.platform_store_subscription (
        subscription_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) UNIQUE NOT NULL,
        tier_id VARCHAR(36) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
        current_period_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        current_period_end TIMESTAMPTZ NOT NULL,
        grace_period_days INTEGER NOT NULL DEFAULT 7,
        payment_verified BOOLEAN NOT NULL DEFAULT TRUE,
        auto_renew BOOLEAN NOT NULL DEFAULT TRUE,
        last_payment_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # platform_billing_invoice
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.platform_billing_invoice (
        invoice_id VARCHAR(36) PRIMARY KEY,
        tenant_id VARCHAR(36) NOT NULL,
        subscription_id VARCHAR(36),
        amount_cents INTEGER NOT NULL DEFAULT 0,
        currency VARCHAR(16) NOT NULL DEFAULT 'INR',
        status VARCHAR(32) NOT NULL DEFAULT 'PAID',
        due_date TIMESTAMPTZ NOT NULL,
        paid_at TIMESTAMPTZ,
        payment_reference VARCHAR(128),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # platform_audit_log
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.platform_audit_log (
        log_id VARCHAR(36) PRIMARY KEY,
        actor_id VARCHAR(36) NOT NULL,
        actor_type VARCHAR(32) NOT NULL DEFAULT 'SUPER_ADMIN',
        action VARCHAR(64) NOT NULL,
        tenant_id VARCHAR(36),
        details JSONB,
        ip_address VARCHAR(64),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # Indexes
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_platform_tenant_status ON public.platform_tenant(status);
    CREATE INDEX IF NOT EXISTS idx_platform_super_admin_email ON public.platform_super_admin(email);
    CREATE INDEX IF NOT EXISTS idx_platform_sub_tenant ON public.platform_store_subscription(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_platform_sub_status ON public.platform_store_subscription(status);
    CREATE INDEX IF NOT EXISTS idx_platform_inv_tenant ON public.platform_billing_invoice(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_platform_inv_status ON public.platform_billing_invoice(status);
    CREATE INDEX IF NOT EXISTS idx_platform_audit_created ON public.platform_audit_log(created_at DESC);
    """)


def downgrade() -> None:
    # Non-destructive downgrade: drops views/indexes only, preserves core table data
    op.execute("""
    DROP INDEX IF EXISTS idx_platform_audit_created;
    DROP INDEX IF EXISTS idx_platform_inv_status;
    DROP INDEX IF EXISTS idx_platform_inv_tenant;
    DROP INDEX IF EXISTS idx_platform_sub_status;
    DROP INDEX IF EXISTS idx_platform_sub_tenant;
    DROP INDEX IF EXISTS idx_platform_super_admin_email;
    DROP INDEX IF EXISTS idx_platform_tenant_status;
    """)

