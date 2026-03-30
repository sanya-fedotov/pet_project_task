"""API tests for user-management endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_payload(**overrides) -> dict:
    """Return a valid user-creation payload with optional overrides."""
    base = {
        "login": f"bot-{uuid.uuid4()}@example.com",
        "password": "secret123",
        "project_id": str(uuid.uuid4()),
        "env": "prod",
        "domain": "regular",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# POST /api/v1/users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_user_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/users returns 201 and the created account (no password)."""
    payload = _user_payload()
    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["login"] == payload["login"]
    assert "password" not in body
    assert "id" in body


@pytest.mark.asyncio
async def test_create_user_duplicate_login(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users returns 409 when the login is already registered."""
    payload = _user_payload(login=test_user.login)
    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_user_requires_auth(async_client: AsyncClient) -> None:
    """POST /api/v1/users returns 401 without an Authorization header."""
    response = await async_client.post("/api/v1/users", json=_user_payload())
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_users(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """GET /api/v1/users returns 200 with at least one account in the list."""
    response = await async_client.get("/api/v1/users", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    logins = [u["login"] for u in body]
    assert test_user.login in logins


# ---------------------------------------------------------------------------
# POST /api/v1/users/lock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lock_user_success(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock returns 200 and a non-null locktime."""
    response = await async_client.post(
        "/api/v1/users/lock",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["locktime"] is not None


@pytest.mark.asyncio
async def test_lock_user_no_free_users(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock returns 404 when every account is locked."""
    # Lock the only available user
    first = await async_client.post("/api/v1/users/lock", headers=auth_headers)
    assert first.status_code == 200

    # Second attempt must fail
    second = await async_client.post("/api/v1/users/lock", headers=auth_headers)
    assert second.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/users/free
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_free_users(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/free returns 200 with freed >= 0."""
    # First lock the test user so there is something to free
    await async_client.post("/api/v1/users/lock", headers=auth_headers)

    response = await async_client.post(
        "/api/v1/users/free",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert "freed" in body
    assert body["freed"] >= 1
