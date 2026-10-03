import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_auth_login_invalid(async_client: AsyncClient):
    response = await async_client.post("/api/auth/login", data={"username": "fake", "password": "fake"})
    assert response.status_code == 401
