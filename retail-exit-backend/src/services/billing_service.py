"""Subscription, Billing & Store Delinquency Service.

Enforces Section 16 of the SEC-OPS V8 Master Prompt:
- Store subscription management & payment verification
- Automated delinquency checks past configurable grace periods
- Automated non-destructive store suspension
- Platform audit logging with actor, reason, and UTC timestamp
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from src.core.multi_tenant import PlatformAsyncSessionLocal
from src.db.platform_models import (
    PlatformTenant,
    PlatformStoreSubscription,
    PlatformBillingInvoice,
    PlatformAuditLog,
    PlatformSubscriptionTier,
    get_utc_now,
)

logger = logging.getLogger("secops.billing")


def ensure_utc(dt: Any) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def run_delinquency_check(actor_id: str = "SYSTEM_BILLING") -> Dict[str, Any]:
    """Scans all active store subscriptions for unverified payments or overdue invoices.
    
    If payment is unverified and past grace period, automatically suspends the store.
    Guarantees: 100% of the tenant's database, ledger history, and snapshots remain intact.
    """
    now = get_utc_now()
    suspended_stores = []
    checked_count = 0

    async with PlatformAsyncSessionLocal() as session:
        # Fetch active store subscriptions
        res = await session.execute(
            select(PlatformStoreSubscription).where(
                PlatformStoreSubscription.status.in_(["ACTIVE", "PAST_DUE"])
            )
        )
        subscriptions = res.scalars().all()
        checked_count = len(subscriptions)

        for sub in subscriptions:
            # Check if subscription has expired and exceeded grace period
            period_end = ensure_utc(sub.current_period_end)
            cutoff_date = period_end + timedelta(days=sub.grace_period_days)
            is_overdue = now > cutoff_date and not sub.payment_verified

            if is_overdue:
                # Update subscription status to SUSPENDED
                sub.status = "SUSPENDED"
                sub.updated_at = now

                # Transition tenant status in PlatformTenant to SUSPENDED
                tenant = await session.get(PlatformTenant, sub.tenant_id)
                if tenant and tenant.status != "SUSPENDED":
                    old_status = tenant.status
                    tenant.status = "SUSPENDED"
                    tenant.updated_at = now

                    # Audit trail entry
                    audit = PlatformAuditLog(
                        actor_id=actor_id,
                        actor_type="SYSTEM",
                        action="AUTO_SUSPEND_DELINQUENT_STORE",
                        tenant_id=sub.tenant_id,
                        details={
                            "reason": f"Payment overdue past {sub.grace_period_days}-day grace period (cutoff: {cutoff_date.isoformat()}).",
                            "previous_status": old_status,
                            "subscription_id": sub.subscription_id,
                        },
                    )
                    session.add(audit)
                    suspended_stores.append(sub.tenant_id)
                    logger.warning(
                        "Store %s automatically SUSPENDED due to delinquency. Data and ledger preserved.",
                        sub.tenant_id,
                    )

        await session.commit()

    return {
        "status": "SUCCESS",
        "checkedSubscriptions": checked_count,
        "suspendedStoresCount": len(suspended_stores),
        "suspendedStoreIds": suspended_stores,
        "timestamp": now.isoformat(),
    }


async def verify_store_payment(
    tenant_id: str,
    amount_cents: int,
    actor_id: str,
    extension_days: int = 30,
) -> Dict[str, Any]:
    """Verifies payment for a store, reactivates if suspended, and extends subscription period."""
    now = get_utc_now()
    async with PlatformAsyncSessionLocal() as session:
        sub_res = await session.execute(
            select(PlatformStoreSubscription).where(PlatformStoreSubscription.tenant_id == tenant_id)
        )
        sub = sub_res.scalar_one_or_none()

        if not sub:
            # Create baseline subscription if missing
            sub = PlatformStoreSubscription(
                tenant_id=tenant_id,
                tier_id="tier_standard",
                status="ACTIVE",
                current_period_start=now,
                current_period_end=now + timedelta(days=extension_days),
                grace_period_days=7,
                payment_verified=True,
                last_payment_at=now,
            )
            session.add(sub)
        else:
            sub.payment_verified = True
            sub.last_payment_at = now
            sub.status = "ACTIVE"
            sub.current_period_start = now
            sub.current_period_end = max(ensure_utc(sub.current_period_end), now) + timedelta(days=extension_days)
            sub.updated_at = now

        # Record billing invoice
        invoice = PlatformBillingInvoice(
            tenant_id=tenant_id,
            subscription_id=sub.subscription_id,
            amount_cents=amount_cents,
            currency="INR",
            status="PAID",
            due_date=now,
            paid_at=now,
        )
        session.add(invoice)

        # Reactivate tenant if it was suspended
        tenant = await session.get(PlatformTenant, tenant_id)
        reactivated = False
        if tenant and tenant.status == "SUSPENDED":
            tenant.status = "ACTIVE"
            tenant.updated_at = now
            reactivated = True

        audit = PlatformAuditLog(
            actor_id=actor_id,
            actor_type="SUPER_ADMIN",
            action="VERIFY_STORE_PAYMENT",
            tenant_id=tenant_id,
            details={
                "amount_cents": amount_cents,
                "reactivated": reactivated,
                "new_period_end": sub.current_period_end.isoformat(),
            },
        )
        session.add(audit)
        await session.commit()

        return {
            "status": "SUCCESS",
            "tenantId": tenant_id,
            "subscriptionStatus": sub.status,
            "periodEnd": sub.current_period_end.isoformat(),
            "reactivated": reactivated,
        }
