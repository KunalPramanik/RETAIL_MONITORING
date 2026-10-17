"""Comprehensive Route Security Lockdown & Authentication Enforcement Tests.

Verifies:
1. All operational data routes enforce mandatory JWT authentication.
2. Only authorized public routes (/health, /metrics, /api/auth/login, etc.) remain publicly accessible.
3. Query-based token authentication works for streaming/snapshot endpoints (?token=<valid_jwt>).
4. Login lockout triggers after configured threshold of failed authentication attempts.
5. Refresh token rotation works and revoked/consumed refresh tokens are rejected.
6. Database reset endpoint requires SUPER_ADMIN, confirmation token, and is protected.
"""

import pytest
from datetime import timedelta
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.core.config import settings
from src.security import (
    create_access_token,
    create_refresh_token,
    revoke_token,
    is_token_revoked,
    reset_failed_logins,
    record_failed_login,
    is_account_locked,
)


@pytest.fixture(autouse=True)
def clean_security_state():
    """Resets failed login history and temporary lockouts before each test."""
    from src.security import _failed_login_history, _lockouts, _revoked_tokens
    _failed_login_history.clear()
    _lockouts.clear()
    _revoked_tokens.clear()
    yield
    _failed_login_history.clear()
    _lockouts.clear()
    _revoked_tokens.clear()


@pytest.mark.asyncio
async def test_allowlisted_public_endpoints_accessible():
    """Verifies that public health, metrics, and documentation endpoints do not require auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Public health check
        res = await ac.get("/health")
        assert res.status_code in (200, 503)

        # Public metrics
        res = await ac.get("/metrics")
        assert res.status_code == 200

        # Public API health ping
        res = await ac.get("/api/health")
        assert res.status_code in (200, 503)


@pytest.mark.asyncio
async def test_data_routes_reject_unauthenticated():
    """Verifies that operational data endpoints strictly reject unauthenticated requests with 401."""
    protected_endpoints = [
        ("GET", "/api/kpis/live"),
        ("GET", "/api/events"),
        ("GET", "/api/alerts"),
        ("GET", "/api/cameras"),
        ("GET", "/api/employees"),
        ("GET", "/api/invoices"),
        ("GET", "/api/inventory/stock"),
        ("GET", "/api/reports/daily"),
        ("GET", "/api/smart-wall/layouts"),
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for method, path in protected_endpoints:
            if method == "GET":
                res = await ac.get(path)
            else:
                res = await ac.post(path)
            assert res.status_code == 401, f"Route {path} did not reject unauthenticated access: status {res.status_code}"
            assert "detail" in res.json()


@pytest.mark.asyncio
async def test_camera_stream_snapshot_accepts_query_token():
    """Verifies that camera streaming endpoints accept ?token=<jwt> parameter for MJPEG <img> tags."""
    token = create_access_token(
        subject="test_supervisor_01",
        role="SUPERVISOR",
        email="supervisor@test.local",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Without token: 401 Unauthorized
        res_no_token = await ac.get("/api/cameras/nonexistent_cam/snapshot")
        assert res_no_token.status_code == 401

        # With query token: passes authentication (fails on missing camera/data, not 401)
        res_with_token = await ac.get(f"/api/cameras/nonexistent_cam/snapshot?token={token}")
        assert res_with_token.status_code != 401, "Query token was not accepted by authentication layer"


@pytest.mark.asyncio
async def test_login_lockout_mechanism():
    """Verifies that consecutive failed logins trigger 429 account lockout."""
    target_user = "operator@store.local"
    max_attempts = getattr(settings.security, "max_login_attempts", 5)

    for i in range(max_attempts - 1):
        attempts, is_locked = record_failed_login(target_user)
        assert not is_locked
        assert attempts == i + 1

    # Nth attempt triggers lockout
    attempts, is_locked = record_failed_login(target_user)
    assert is_locked
    assert attempts == max_attempts

    # Further checks report locked
    locked, rem = is_account_locked(target_user)
    assert locked
    assert rem > 0

    # Successful login clears lockout
    reset_failed_logins(target_user)
    locked, _ = is_account_locked(target_user)
    assert not locked


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_revocation():
    """Verifies that refresh tokens rotate properly and used tokens are revoked."""
    refresh_token = create_refresh_token(
        subject="test_user_99",
        role="SUPERVISOR",
        email="supervisor@test.local",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Successful rotation
        res = await ac.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        new_refresh = data["refresh_token"]

        # 2. Old refresh token is now revoked
        assert is_token_revoked(refresh_token)
        res_replay = await ac.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert res_replay.status_code == 401

        # 3. New refresh token can be rotated again
        res_rotate_again = await ac.post("/api/auth/refresh", json={"refresh_token": new_refresh})
        assert res_rotate_again.status_code == 200


@pytest.mark.asyncio
async def test_reset_database_security_controls():
    """Verifies that /api/settings/reset-database requires SUPER_ADMIN and confirmation token."""
    # 1. Unauthenticated -> 401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/settings/reset-database")
        assert res.status_code == 401

    # 2. Viewer or Supervisor -> 403 Forbidden
    supervisor_token = create_access_token(
        subject="supervisor_01",
        role="SUPERVISOR",
        email="supervisor@test.local",
    )
    headers = {"Authorization": f"Bearer {supervisor_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/settings/reset-database", headers=headers)
        assert res.status_code == 403

    # 3. Super admin without confirmation token -> 400 Bad Request
    superadmin_token = create_access_token(
        subject="owner_01",
        role="SUPER_ADMIN",
        email="owner@secops.local",
    )
    admin_headers = {"Authorization": f"Bearer {superadmin_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/settings/reset-database",
            headers=admin_headers,
            json={"confirmation_token": "WRONG_TOKEN"},
        )
        assert res.status_code == 400

