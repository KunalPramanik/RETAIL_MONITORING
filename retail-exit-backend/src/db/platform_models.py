"""Platform Control-Plane Database Models.

Stores platform-level records ONLY:
- Multi-company / Tenant Registry
- Platform Super Admin accounts
- Platform-level audit trail

Strictly isolated from tenant operational databases (cameras, frames, stock, events).
Enforces Section 3 of the V8 Master Prompt.
"""

from typing import Any, Optional
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON, CheckConstraint, Integer
from sqlalchemy.orm import declarative_base

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

def generate_uuid() -> str:
    return str(uuid.uuid4())

PlatformBase = declarative_base()


class PlatformTenant(PlatformBase):
    """Platform Tenant / Company Registry record."""
    __tablename__ = "platform_tenant"

    tenant_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    name: Any = Column(String(255), unique=True, nullable=False)
    slug: Any = Column(String(64), unique=True, nullable=False, index=True)
    db_identifier: Any = Column(String(255), unique=True, nullable=False)
    status: Any = Column(String(32), nullable=False, default="PROVISIONING", index=True)
    timezone: Any = Column(String(64), nullable=False, default="Asia/Kolkata")
    currency: Any = Column(String(16), nullable=False, default="INR")
    contact_email: Any = Column(String(255), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PROVISIONING', 'ACTIVE', 'SUSPENDED', 'DECOMMISSIONED')",
            name="chk_platform_tenant_status",
        ),
    )


class PlatformSuperAdmin(PlatformBase):
    """Platform-level Master Super Admin account."""
    __tablename__ = "platform_super_admin"

    admin_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    username: Any = Column(String(64), unique=True, nullable=False, index=True)
    email: Any = Column(String(255), unique=True, nullable=False, index=True)
    password_hash: Any = Column(String(255), nullable=False)
    role: Any = Column(String(32), nullable=False, default="SUPER_ADMIN")
    is_active: Any = Column(Boolean, nullable=False, default=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    last_login_at: Any = Column(DateTime(timezone=True), nullable=True)


class PlatformAuditLog(PlatformBase):
    """Platform-level immutable audit log."""
    __tablename__ = "platform_audit_log"

    log_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    actor_id: Any = Column(String(36), nullable=False)
    actor_type: Any = Column(String(32), nullable=False, default="SUPER_ADMIN")
    action: Any = Column(String(64), nullable=False, index=True)
    tenant_id: Any = Column(String(36), nullable=True, index=True)
    details: Any = Column(JSON, nullable=True)
    ip_address: Any = Column(String(64), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)


class PlatformSubscriptionTier(PlatformBase):
    """Platform subscription tier / plan definition."""
    __tablename__ = "platform_subscription_tier"

    tier_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    name: Any = Column(String(64), unique=True, nullable=False)
    max_cameras: Any = Column(Integer, nullable=False, default=4)
    price_cents: Any = Column(Integer, nullable=False, default=0)
    currency: Any = Column(String(16), nullable=False, default="INR")
    billing_cycle: Any = Column(String(16), nullable=False, default="MONTHLY")
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)


class PlatformStoreSubscription(PlatformBase):
    """Store tenant subscription and payment verification record."""
    __tablename__ = "platform_store_subscription"

    subscription_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Any = Column(String(36), unique=True, nullable=False, index=True)
    tier_id: Any = Column(String(36), nullable=False)
    status: Any = Column(String(32), nullable=False, default="ACTIVE", index=True)
    current_period_start: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    current_period_end: Any = Column(DateTime(timezone=True), nullable=False)
    grace_period_days: Any = Column(Integer, nullable=False, default=7)
    payment_verified: Any = Column(Boolean, nullable=False, default=True)
    auto_renew: Any = Column(Boolean, nullable=False, default=True)
    last_payment_at: Any = Column(DateTime(timezone=True), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'PAST_DUE', 'SUSPENDED', 'CANCELLED')",
            name="chk_platform_sub_status",
        ),
    )


class PlatformBillingInvoice(PlatformBase):
    """Platform billing invoice record for store subscriptions."""
    __tablename__ = "platform_billing_invoice"

    invoice_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Any = Column(String(36), nullable=False, index=True)
    subscription_id: Any = Column(String(36), nullable=True)
    amount_cents: Any = Column(Integer, nullable=False, default=0)
    currency: Any = Column(String(16), nullable=False, default="INR")
    status: Any = Column(String(32), nullable=False, default="PAID", index=True)
    due_date: Any = Column(DateTime(timezone=True), nullable=False)
    paid_at: Any = Column(DateTime(timezone=True), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PAID', 'UNPAID', 'DELINQUENT', 'VOID')",
            name="chk_platform_invoice_status",
        ),
    )


