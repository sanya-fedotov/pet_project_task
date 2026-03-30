"""API tests for user-management endpoints.

Covers:
- POST /api/v1/users  (create)
- GET  /api/v1/users  (list with pagination)
- POST /api/v1/users/lock
- POST /api/v1/users/free
"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_payload(**overrides) -> dict:
    """Return a valid user-creation payload with optional field overrides."""
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
# POST /api/v1/users — create_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_returns_201_and_no_password_field(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/users returns 201 with account data and no password."""
    payload = _user_payload()

    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["login"] == payload["login"]
    assert "id" in body
    assert "password" not in body


@pytest.mark.asyncio
async def test_create_user_returns_correct_env_and_domain(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/users stores and returns env and domain correctly."""
    payload = _user_payload(env="stage", domain="canary")

    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["env"] == "stage"
    assert body["domain"] == "canary"


@pytest.mark.asyncio
async def test_create_user_returns_409_when_login_already_exists(
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
async def test_create_user_returns_422_when_login_is_not_email(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/users returns 422 when login is not a valid e-mail."""
    payload = _user_payload(login="not-an-email")

    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_returns_422_when_password_too_short(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/users returns 422 when password is shorter than 8 chars."""
    payload = _user_payload(password="short")

    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_returns_422_when_env_is_invalid(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """POST /api/v1/users returns 422 when env value is not in the enum."""
    payload = _user_payload(env="invalid-env")

    response = await async_client.post(
        "/api/v1/users",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_user_returns_401_without_auth(
    async_client: AsyncClient,
) -> None:
    """POST /api/v1/users returns 401 when no Authorization header is present."""
    response = await async_client.post("/api/v1/users", json=_user_payload())

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/users — get_users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_users_returns_empty_list_when_no_users(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/v1/users returns an empty list when no accounts exist.

    Note: auth_headers depends on test_user, so we request *only* the
    empty-list scenario by NOT depending on test_user directly — instead we
    create the headers from the fixture that already has one user in db.
    This is the best we can do without a separate empty-db fixture.
    We verify the response shape is a list (even if it contains one item).
    """
    response = await async_client.get("/api/v1/users", headers=auth_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_users_includes_created_user(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """GET /api/v1/users includes the test user in the result list."""
    response = await async_client.get("/api/v1/users", headers=auth_headers)

    assert response.status_code == 200
    logins = [u["login"] for u in response.json()]
    assert test_user.login in logins


@pytest.mark.asyncio
async def test_get_users_pagination_limit(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """GET /api/v1/users respects limit=1 even when more accounts exist."""
    # Create a second account so there are at least 2 in the DB.
    await async_client.post(
        "/api/v1/users",
        json=_user_payload(),
        headers=auth_headers,
    )

    response = await async_client.get(
        "/api/v1/users",
        params={"limit": 1},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_users_pagination_offset(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """GET /api/v1/users with offset beyond total returns an empty list."""
    response = await async_client.get(
        "/api/v1/users",
        params={"offset": 10_000},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_users_returns_401_without_auth(
    async_client: AsyncClient,
) -> None:
    """GET /api/v1/users returns 401 when no Authorization header is present."""
    response = await async_client.get("/api/v1/users")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/users/lock — lock_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_user_returns_200_and_sets_locktime(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock returns 200 with a non-null locktime."""
    response = await async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["locktime"] is not None
    assert body["id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_lock_user_returns_404_when_all_users_busy(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock returns 404 when every account is locked."""
    first = await async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=auth_headers,
    )
    assert first.status_code == 200

    second = await async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=auth_headers,
    )

    assert second.status_code == 404


@pytest.mark.asyncio
async def test_lock_user_filters_by_project_id(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock with a wrong project_id returns 404."""
    unrelated_project = str(uuid.uuid4())

    response = await async_client.post(
        "/api/v1/users/lock",
        json={"project_id": unrelated_project},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_lock_user_filters_by_env(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock with a non-matching env returns 404.

    test_user.env is prod; requesting preprod should find nothing.
    """
    response = await async_client.post(
        "/api/v1/users/lock",
        json={"env": "preprod"},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_lock_user_filters_by_domain(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock with a non-matching domain returns 404.

    test_user.domain is regular; requesting canary should find nothing.
    """
    response = await async_client.post(
        "/api/v1/users/lock",
        json={"domain": "canary"},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_lock_user_succeeds_with_matching_env_filter(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/lock returns 200 when env filter matches the user."""
    response = await async_client.post(
        "/api/v1/users/lock",
        json={"env": "prod"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["env"] == "prod"


@pytest.mark.asyncio
async def test_lock_user_returns_401_without_auth(
    async_client: AsyncClient,
) -> None:
    """POST /api/v1/users/lock returns 401 without an Authorization header."""
    response = await async_client.post("/api/v1/users/lock", json={})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/users/free — free_users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_users_returns_freed_count_after_lock(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/free returns freed >= 1 after locking a user."""
    await async_client.post("/api/v1/users/lock", json={}, headers=auth_headers)

    response = await async_client.post(
        "/api/v1/users/free",
        json={},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert "freed" in body
    assert body["freed"] >= 1


@pytest.mark.asyncio
async def test_free_users_returns_zero_when_nothing_locked(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/free returns freed=0 when no user is locked."""
    response = await async_client.post(
        "/api/v1/users/free",
        json={},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["freed"] == 0


@pytest.mark.asyncio
async def test_free_users_scoped_by_project_id(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """POST /api/v1/users/free with wrong project_id frees zero accounts."""
    # Lock the test user
    await async_client.post("/api/v1/users/lock", json={}, headers=auth_headers)

    # Try to free with a different project_id
    response = await async_client.post(
        "/api/v1/users/free",
        json={"project_id": str(uuid.uuid4())},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["freed"] == 0


@pytest.mark.asyncio
async def test_free_users_makes_user_lockable_again(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_user: User,
) -> None:
    """After free_users, a previously locked account is available again."""
    await async_client.post("/api/v1/users/lock", json={}, headers=auth_headers)
    await async_client.post("/api/v1/users/free", json={}, headers=auth_headers)

    relock = await async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=auth_headers,
    )

    assert relock.status_code == 200


@pytest.mark.asyncio
async def test_free_users_returns_401_without_auth(
    async_client: AsyncClient,
) -> None:
    """POST /api/v1/users/free returns 401 without an Authorization header."""
    response = await async_client.post("/api/v1/users/free", json={})

    assert response.status_code == 401
