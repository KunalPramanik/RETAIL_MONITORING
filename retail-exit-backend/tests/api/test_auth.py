"""Automated Integration Tests for SEC-OPS Authentication & Authorization

Tests both email-based and username-based login paths, token issuance,
incorrect credential handling, and operator profile retrieval.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_auth_login_invalid(async_client: AsyncClient):
    response = await async_client.post("/api/auth/login", data={"username": "fake", "password": "fake"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_auth_registration_and_login_flows(async_client: AsyncClient):
    # 1. Register a user with username
    reg_payload = {
        "username": "operator_jane",
        "email": "jane@secops.local",
        "password": "Password123!",
        "role": "SUPERVISOR",
    }
    reg_resp = await async_client.post("/api/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201, reg_resp.text
    data = reg_resp.json()
    assert data["username"] == "operator_jane"
    assert data["email"] == "jane@secops.local"
    assert data["role"] == "SUPERVISOR"

    # 2. Login using username
    login_user_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "operator_jane", "password": "Password123!"},
    )
    assert login_user_resp.status_code == 200, login_user_resp.text
    token_data = login_user_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]

    # 3. Login using email
    login_email_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "jane@secops.local", "password": "Password123!"},
    )
    assert login_email_resp.status_code == 200, login_email_resp.text
    assert "access_token" in login_email_resp.json()

    # 4. Reject invalid password
    bad_pass_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "operator_jane", "password": "WrongPassword999"},
    )
    assert bad_pass_resp.status_code == 401

    # 5. Reject nonexistent user
    unknown_user_resp = await async_client.post(
        "/api/auth/login",
        data={"username": "nonexistent_ghost", "password": "Password123!"},
    )
    assert unknown_user_resp.status_code == 401

    # 6. Verify /me endpoint with Bearer token
    me_resp = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200, me_resp.text
    me_data = me_resp.json()
    assert me_data["username"] == "operator_jane"
    assert me_data["email"] == "jane@secops.local"
    assert me_data["role"] == "SUPERVISOR"
