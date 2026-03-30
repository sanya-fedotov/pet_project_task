"""PostgreSQL integration tests for the lock/free endpoints.

These tests run against a real PostgreSQL instance (via testcontainers) so
that ``SELECT FOR UPDATE SKIP LOCKED`` is exercised end-to-end.  They are
separate from the SQLite-backed tests in ``test_users.py`` because SQLite does
not support row-level advisory locks.
"""

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_lock_skip_locked_returns_404_when_all_locked(
    pg_async_client: AsyncClient,
    pg_auth_headers: dict[str, str],
    pg_test_user: User,
) -> None:
    """Verify that SELECT FOR UPDATE SKIP LOCKED prevents double-locking.

    This test requires a real PostgreSQL database; it will not pass against
    SQLite, which silently ignores the SKIP LOCKED clause.
    """
    # First lock succeeds
    first = await pg_async_client.post(
        "/api/v1/users/lock",
        headers=pg_auth_headers,
    )
    assert first.status_code == 200
    assert first.json()["locktime"] is not None

    # Second lock must fail — the only user is already locked
    second = await pg_async_client.post(
        "/api/v1/users/lock",
        headers=pg_auth_headers,
    )
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_free_users_releases_lock(
    pg_async_client: AsyncClient,
    pg_auth_headers: dict[str, str],
    pg_test_user: User,
) -> None:
    """After free_users, the previously locked account must be lockable again."""
    # Lock the user
    lock_resp = await pg_async_client.post(
        "/api/v1/users/lock",
        headers=pg_auth_headers,
    )
    assert lock_resp.status_code == 200

    # Free all users
    free_resp = await pg_async_client.post(
        "/api/v1/users/free",
        headers=pg_auth_headers,
    )
    assert free_resp.status_code == 200
    assert free_resp.json()["freed"] >= 1

    # Should be lockable again now
    relock_resp = await pg_async_client.post(
        "/api/v1/users/lock",
        headers=pg_auth_headers,
    )
    assert relock_resp.status_code == 200
