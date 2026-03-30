"""PostgreSQL integration tests for the lock/free endpoints.

These tests run against a real PostgreSQL instance (via testcontainers) to
exercise ``SELECT FOR UPDATE SKIP LOCKED`` end-to-end.  SQLite silently
ignores the SKIP LOCKED clause, so this file is the only place where the
true atomicity guarantee is verified.

The ``loop_scope="session"`` marker ensures every test in this module shares
the same asyncio event loop as the session-scoped ``pg_engine`` fixture,
avoiding the "Future attached to a different loop" error that asyncpg raises
when a connection created on one loop is awaited on another.
"""

import pytest
from httpx import AsyncClient

from app.models.user import User

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_lock_skip_locked_returns_404_when_all_locked(
    pg_async_client: AsyncClient,
    pg_auth_headers: dict[str, str],
    pg_test_user: User,
) -> None:
    """SELECT FOR UPDATE SKIP LOCKED prevents a second caller from double-locking.

    The first lock call succeeds and sets locktime.  The second call must get
    a 404 because the only matching row is still held by the open transaction.
    """
    first = await pg_async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=pg_auth_headers,
    )
    assert first.status_code == 200
    assert first.json()["locktime"] is not None

    second = await pg_async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=pg_auth_headers,
    )
    assert second.status_code == 404


async def test_free_users_releases_lock(
    pg_async_client: AsyncClient,
    pg_auth_headers: dict[str, str],
    pg_test_user: User,
) -> None:
    """After free_users, the previously locked account is lockable again."""
    lock_resp = await pg_async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=pg_auth_headers,
    )
    assert lock_resp.status_code == 200

    free_resp = await pg_async_client.post(
        "/api/v1/users/free",
        json={},
        headers=pg_auth_headers,
    )
    assert free_resp.status_code == 200
    assert free_resp.json()["freed"] >= 1

    relock_resp = await pg_async_client.post(
        "/api/v1/users/lock",
        json={},
        headers=pg_auth_headers,
    )
    assert relock_resp.status_code == 200
