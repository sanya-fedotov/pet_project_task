"""Unit tests for the botfarm service layer.

Business logic is verified directly against the SQLite in-memory database
via the ``db_session`` fixture — no HTTP layer is involved.

Scenarios covered:
- Password hashing on creation
- Response never exposes password
- lock_user sets locktime
- lock_user raises 404 when all users busy
- lock_user re-acquires an expired lock
- free_users clears locktime and returns the correct count
- free_users scoped by project_id only releases matching accounts
- Duplicate login raises 409
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
from app.schemas.user import FreeUsersRequest, LockUserRequest, UserCreate
from app.services import botfarm as service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_create(**overrides) -> UserCreate:
    """Return a valid :class:`UserCreate` with optional field overrides."""
    defaults: dict = {
        "login": f"bot-{uuid.uuid4()}@example.com",
        "password": "secret123",
        "project_id": uuid.uuid4(),
        "env": EnvType.prod,
        "domain": DomainType.regular,
    }
    defaults.update(overrides)
    return UserCreate(**defaults)


def _lock_request(**kwargs) -> LockUserRequest:
    """Return a :class:`LockUserRequest` with optional filters."""
    return LockUserRequest(**kwargs)


def _free_request(**kwargs) -> FreeUsersRequest:
    """Return a :class:`FreeUsersRequest` with optional project filter."""
    return FreeUsersRequest(**kwargs)


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def free_user(db_session: AsyncSession) -> UserModel:
    """Persist and return a free (unlocked) user in the SQLite DB."""
    schema = _make_user_create()
    response = await service.create_user(db_session, schema)
    result = await db_session.execute(
        select(UserModel).where(UserModel.id == response.id)
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_hashes_password(db_session: AsyncSession) -> None:
    """Password stored in the DB must be a bcrypt hash, never plain text."""
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
async def test_create_user_raises_409_when_login_already_exists(
    db_session: AsyncSession,
) -> None:
    """create_user raises 409 HTTPException when the login is a duplicate."""
    schema = _make_user_create()
    await service.create_user(db_session, schema)

    duplicate = _make_user_create(login=str(schema.login))

    with pytest.raises(HTTPException) as exc_info:
        await service.create_user(db_session, duplicate)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# lock_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_user_sets_locktime_to_recent_utc(
    db_session: AsyncSession,
    free_user: UserModel,
) -> None:
    """lock_user must set locktime to a recent UTC timestamp."""
    before = datetime.now(timezone.utc)

    response = await service.lock_user(db_session, _lock_request())

    after = datetime.now(timezone.utc)
    assert response.locktime is not None

    locktime = response.locktime
    if locktime.tzinfo is None:
        locktime = locktime.replace(tzinfo=timezone.utc)

    assert before <= locktime <= after


@pytest.mark.asyncio
async def test_lock_user_raises_404_when_all_users_busy(
    db_session: AsyncSession,
) -> None:
    """lock_user raises 404 HTTPException when no free account is available."""
    schema = _make_user_create()
    await service.create_user(db_session, schema)
    await service.lock_user(db_session, _lock_request())  # lock the only user

    with pytest.raises(HTTPException) as exc_info:
        await service.lock_user(db_session, _lock_request())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_lock_user_reacquires_expired_lock(db_session: AsyncSession) -> None:
    """A user whose locktime is older than TTL must be available again."""
    schema = _make_user_create()
    created = await service.create_user(db_session, schema)

    # Manually set a locktime 1 hour in the past (guaranteed expired).
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db_session.execute(
        select(UserModel).where(UserModel.id == created.id)
    )
    user_orm = result.scalar_one()
    user_orm.locktime = expired_time
    await db_session.flush()

    locked = await service.lock_user(db_session, _lock_request())

    assert locked.id == created.id
    assert locked.locktime is not None
    # The new locktime must be recent, not the old expired one.
    new_locktime = locked.locktime
    if new_locktime.tzinfo is None:
        new_locktime = new_locktime.replace(tzinfo=timezone.utc)
    assert new_locktime > expired_time


@pytest.mark.asyncio
async def test_lock_user_filters_by_project_id(db_session: AsyncSession) -> None:
    """lock_user with a project_id filter ignores users in other projects."""
    await service.create_user(db_session, _make_user_create())  # unrelated project

    with pytest.raises(HTTPException) as exc_info:
        await service.lock_user(
            db_session, _lock_request(project_id=uuid.uuid4())
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_lock_user_filters_by_env(db_session: AsyncSession) -> None:
    """lock_user with an env filter ignores users with a different env."""
    await service.create_user(db_session, _make_user_create(env=EnvType.prod))

    with pytest.raises(HTTPException) as exc_info:
        await service.lock_user(
            db_session, _lock_request(env=EnvType.preprod)
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_lock_user_filters_by_domain(db_session: AsyncSession) -> None:
    """lock_user with a domain filter ignores users with a different domain."""
    await service.create_user(
        db_session, _make_user_create(domain=DomainType.regular)
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.lock_user(
            db_session, _lock_request(domain=DomainType.canary)
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# free_users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_users_clears_locktime_and_returns_count(
    db_session: AsyncSession,
    free_user: UserModel,
) -> None:
    """free_users must set locktime to NULL and report the freed count."""
    await service.lock_user(db_session, _lock_request())

    result = await service.free_users(db_session, _free_request())

    assert result.freed >= 1

    db_result = await db_session.execute(
        select(UserModel).where(UserModel.id == free_user.id)
    )
    refreshed = db_result.scalar_one()
    assert refreshed.locktime is None


@pytest.mark.asyncio
async def test_free_users_returns_zero_when_nothing_locked(
    db_session: AsyncSession,
    free_user: UserModel,
) -> None:
    """free_users returns freed=0 when no user has a locktime set."""
    result = await service.free_users(db_session, _free_request())

    assert result.freed == 0


@pytest.mark.asyncio
async def test_free_users_scoped_to_project_only_frees_matching(
    db_session: AsyncSession,
) -> None:
    """free_users with project_id only releases accounts in that project."""
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()

    user_a_resp = await service.create_user(
        db_session, _make_user_create(project_id=project_a)
    )
    user_b_resp = await service.create_user(
        db_session, _make_user_create(project_id=project_b)
    )

    # Lock both users.
    await service.lock_user(db_session, _lock_request(project_id=project_a))
    await service.lock_user(db_session, _lock_request(project_id=project_b))

    # Free only project_a.
    freed_result = await service.free_users(
        db_session, _free_request(project_id=project_a)
    )
    assert freed_result.freed == 1

    # Verify user_a is now free.
    res_a = await db_session.execute(
        select(UserModel).where(UserModel.id == user_a_resp.id)
    )
    assert res_a.scalar_one().locktime is None

    # Verify user_b is still locked.
    res_b = await db_session.execute(
        select(UserModel).where(UserModel.id == user_b_resp.id)
    )
    assert res_b.scalar_one().locktime is not None
