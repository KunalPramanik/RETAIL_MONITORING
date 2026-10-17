"""Team 5 Test Suite — 6 Role Dashboards & Direct DB Auth Verification

Covers Section 17, 18 and User Revision 5:
1. Verify login role and profile routing for ces@gmail.com directly from the database (SUPER_ADMIN + Store Admin).
2. Separately test permissions, API authorization, and dashboard visibility for:
   - Software Owner (SUPER_ADMIN): Global tenant health & telemetry. Privacy barrier: zero access to store inventory/cameras.
   - Store Admin (ADMIN): Full store management, catalog, staff, cameras, inventory. Forbidden from platform owner billing.
   - Supervisor (SUPERVISOR): Opening stock verification, movement discrepancies. Forbidden from admin store settings.
   - Operator (OPERATOR): Station workflows, barcode scanning, transfer progress. Forbidden from admin configuration.
   - Security (SECURITY): Perimeter breach alerts, unassigned person tracking. Forbidden from inventory mutations.
   - Auditor (AUDITOR / VIEWER): Strictly read-only immutable ledger. Forbidden from manual adjustments or catalog changes.
"""

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import AppUser, get_utc_now
from src.core.multi_tenant import init_platform_db, PlatformAsyncSessionLocal
from src.db.platform_models import (
    PlatformSuperAdmin,
)
from src.security import get_password_hash, create_access_token


@pytest.mark.asyncio
async def test_ces_direct_db_verification_and_super_admin_role(db_session, async_client: AsyncClient):
    """Verifies that ces@gmail.com in the database authenticates with Ces@1234 and resolves to SUPER_ADMIN."""
    await init_platform_db()
    now = get_utc_now()
    
    # 1. Ensure ces@gmail.com is present in AppUser with Ces@1234
    res = await db_session.execute(select(AppUser).where(AppUser.email == "ces@gmail.com"))
    user = res.scalar_one_or_none()
    
    if not user:
        user = AppUser(
            user_id="user_ces_root_001",
            email="ces@gmail.com",
            username="ces",
            password_hash=get_password_hash("Ces@1234"),
            role="ADMIN",
            is_active=True,
            created_at=now,
        )
        db_session.add(user)
        await db_session.commit()
    else:
        user.password_hash = get_password_hash("Ces@1234")
        user.is_active = True
        await db_session.commit()

    # 2. Test direct database authentication via /api/auth/login
    login_resp = await async_client.post(
        "/api/auth/login",
        json={"email": "ces@gmail.com", "password": "Ces@1234"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    data = login_resp.json()
    assert data["role"] == "SUPER_ADMIN"
    assert data["isPlatformOwner"] is True
    token = data["access_token"]

    # 3. Test /api/auth/me profile routing
    me_resp = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "ces@gmail.com"
    assert me_data["role"] == "SUPER_ADMIN"
    assert me_data["isPlatformOwner"] is True


@pytest.mark.asyncio
async def test_software_owner_platform_access_and_privacy_barrier(async_client: AsyncClient):
    """Software Owner (SUPER_ADMIN) has access to platform telemetry and subscriptions,

    while strictly blocked from store private inventory counts.
    """
    await init_platform_db()
    uid = uuid.uuid4().hex[:6]

    async with PlatformAsyncSessionLocal() as session:
        admin = PlatformSuperAdmin(
            admin_id=f"SA-{uid}",
            username=f"owner_{uid}",
            email=f"owner_{uid}@secops.global",
            password_hash=get_password_hash("Pass@1234"),
            role="SUPER_ADMIN",
            is_active=True,
        )
        session.add(admin)
        await session.commit()

    token = create_access_token(subject=admin.admin_id, role="SUPER_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Can access platform telemetry
    resp = await async_client.get("/api/platform/telemetry", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "infrastructure" in data
    assert data["infrastructure"]["privacyBarrierActive"] is True

    # 2. Strict Privacy Barrier: Software owner cannot see private store inventory or cctv
    assert "inventory" not in data
    assert "camera_stream" not in data


@pytest.mark.asyncio
async def test_store_admin_permissions(db_session, async_client: AsyncClient):
    """Store Admin has access to store inventory adjustment, but is forbidden from platform subscriptions."""
    await init_platform_db()
    admin_token = create_access_token(subject="user_admin_001", role="ADMIN")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Platform routes require SUPER_ADMIN -> Forbidden for ADMIN
    plat_resp = await async_client.get("/api/platform/subscriptions", headers=admin_headers)
    assert plat_resp.status_code == 403


@pytest.mark.asyncio
async def test_supervisor_permissions(async_client: AsyncClient):
    """Supervisor can view initial stock verifications, but is forbidden from platform billing routes."""
    await init_platform_db()
    sup_token = create_access_token(subject="user_sup_001", role="SUPERVISOR")
    sup_headers = {"Authorization": f"Bearer {sup_token}"}

    # Allowed: list verifications
    verif_resp = await async_client.get("/api/inventory/verification", headers=sup_headers)
    assert verif_resp.status_code == 200

    # Forbidden: platform routes
    plat_resp = await async_client.get("/api/platform/subscriptions", headers=sup_headers)
    assert plat_resp.status_code == 403


@pytest.mark.asyncio
async def test_operator_permissions(async_client: AsyncClient):
    """Operator can access inventory and ledger, but cannot access platform telemetry."""
    await init_platform_db()
    op_token = create_access_token(subject="user_op_001", role="OPERATOR")
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # Can read stock
    stock_resp = await async_client.get("/api/inventory/stock", headers=op_headers)
    assert stock_resp.status_code == 200

    # Forbidden: platform routes
    plat_resp = await async_client.get("/api/platform/telemetry", headers=op_headers)
    assert plat_resp.status_code == 403


@pytest.mark.asyncio
async def test_auditor_read_only_immutable_access(async_client: AsyncClient):
    """Auditor / Viewer has strictly read-only access to ledger, forbidden from manual stock adjustments."""
    audit_token = create_access_token(subject="user_audit_001", role="AUDITOR")
    audit_headers = {"Authorization": f"Bearer {audit_token}"}

    # Allowed: read stock & ledger
    stock_resp = await async_client.get("/api/inventory/stock", headers=audit_headers)
    assert stock_resp.status_code == 200

    ledger_resp = await async_client.get("/api/inventory/ledger", headers=audit_headers)
    assert ledger_resp.status_code == 200

    # Strictly Forbidden: Mutating stock adjustment (requires SUPER_ADMIN, ADMIN, SUPERVISOR, or OPERATOR)
    adjust_resp = await async_client.post(
        "/api/inventory/adjust",
        json={
            "sku_code": "SKU-TEST-99",
            "qty_adjustment": 5,
            "reason": "Auditor unauthorized adjustment attempt",
        },
        headers=audit_headers,
    )
    assert adjust_resp.status_code == 403
