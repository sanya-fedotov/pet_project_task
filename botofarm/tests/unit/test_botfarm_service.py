"""Unit tests for the botfarm service layer.

These tests verify business logic in isolation by operating directly against
the in-memory SQLite database via the ``db_session`` fixture — no HTTP layer
is involved.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import DomainType, EnvType
from app.models.user import User as UserModel
from app.schemas.user import UserCreate
from app.services import botfarm as service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user_create(**overrides) -> UserCreate:
    """Return a valid :class:`UserCreate` with optional field overrides."""
    defaults = {
        "login": f"bot-{uuid.uuid4()}@example.com",
        "password": "secret123",
        "project_id": uuid.uuid4(),
        "env": EnvType.prod,
        "domain": DomainType.regular,
    }
    defaults.update(overrides)
    return UserCreate(**defaults)


@pytest_asyncio.fixture()
async def free_user(db_session: AsyncSession) -> UserModel:
    """Persist and return a free (unlocked) user."""
    schema = _make_user_create()
    response = await service.create_user(db_session, schema)
    # Fetch the ORM instance for direct field inspection
    result = await db_session.execute(
        select(UserModel).where(UserModel.id == response.id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_user_hashes_password(db_session: AsyncSession) -> None:
    """Password stored in the DB must be a bcrypt hash, not plain text."""
    schema = _make_user_create(password="plainpassword")
    response = await service.create_user(db_session, schema)

    result = await db_session.execute(
        select(UserModel).where(UserModel.id == response.id)
    )
    user_orm = result.scalar_one()

    assert user_orm.password != "plainpassword"
    assert verify_password("plainpassword", user_orm.password)


@pytest.mark.asyncio
async def test_create_user_response_has_no_password_field(
    db_session: AsyncSession,
) -> None:
    """UserResponse must not expose the password attribute."""
    schema = _make_user_create()
    response = await service.create_user(db_session, schema)
    assert not hasattr(response, "password")


@pytest.mark.asyncio
async def test_lock_user_sets_locktime(
    db_session: AsyncSession,
    free_user: UserModel,
) -> None:
    """lock_user must set locktime to a recent UTC timestamp."""
    before = datetime.now(timezone.utc)
    response = await service.lock_user(db_session)
    after = datetime.now(timezone.utc)

    assert response.locktime is not None
    # Make both tz-aware for comparison
    locktime = response.locktime
    if locktime.tzinfo is None:
        locktime = locktime.replace(tzinfo=timezone.utc)

    assert before <= locktime <= after


@pytest.mark.asyncio
async def test_lock_user_skips_locked(db_session: AsyncSession) -> None:
    """When the only user is currently locked, lock_user must raise 404."""
    # Create one user and immediately lock it
    schema = _make_user_create()
    await service.create_user(db_session, schema)
    await service.lock_user(db_session)  # first call succeeds

    # Second call must fail — no free accounts remain
    with pytest.raises(HTTPException) as exc_info:
        await service.lock_user(db_session)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_free_users_clears_locktime(
    db_session: AsyncSession,
    free_user: UserModel,
) -> None:
    """free_users must set locktime to NULL and return the correct count."""
    # Lock the user first
    await service.lock_user(db_session)

    result = await service.free_users(db_session)
    assert result.freed >= 1

    # Verify in DB that locktime is cleared
    db_result = await db_session.execute(
        select(UserModel).where(UserModel.id == free_user.id)
    )
    refreshed = db_result.scalar_one()
    assert refreshed.locktime is None


@pytest.mark.asyncio
async def test_lock_user_reacquires_expired_lock(db_session: AsyncSession) -> None:
    """A user whose lock has expired must be available for locking again."""
    schema = _make_user_create()
    created = await service.create_user(db_session, schema)

    # Manually set an expired locktime (1 hour ago)
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db_session.execute(
        select(UserModel).where(UserModel.id == created.id)
    )
    user_orm = result.scalar_one()
    user_orm.locktime = expired_time
    await db_session.flush()

    # Should succeed because the lock is expired
    locked = await service.lock_user(db_session)
    assert locked.id == created.id
    assert locked.locktime is not None
