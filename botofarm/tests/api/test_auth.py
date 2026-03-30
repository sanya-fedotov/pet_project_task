"""API tests for the authentication endpoint."""

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user: User) -> None:
    """POST /api/v1/auth/token returns a bearer token for valid credentials."""
    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": test_user.login, "password": "testpassword"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, test_user: User) -> None:
    """POST /api/v1/auth/token returns 401 for an incorrect password."""
    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": test_user.login, "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(async_client: AsyncClient) -> None:
    """POST /api/v1/auth/token returns 401 for an unknown login."""
    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_requires_token(async_client: AsyncClient) -> None:
    """Endpoints protected by get_current_user return 401 without a token."""
    response = await async_client.post("/api/v1/users/lock")
    assert response.status_code == 401
