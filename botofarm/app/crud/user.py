"""Data-access layer: all direct database interactions for the User model."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate


async def create_user(
    db: AsyncSession, user_create: UserCreate, hashed_password: str
) -> User:
    """Persist a new User record.

    Args:
        db: Active async database session.
        user_create: Validated creation schema (login, project_id, env, domain).
        hashed_password: Pre-hashed bcrypt password string.

    Returns:
        The newly created :class:`~app.models.user.User` ORM instance.
    """
    user = User(
        id=uuid.uuid4(),
        login=str(user_create.login),
        password=hashed_password,
        project_id=user_create.project_id,
        env=user_create.env,
        domain=user_create.domain,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def get_user_by_login(db: AsyncSession, login: str) -> User | None:
    """Fetch a single user by their login e-mail.

    Args:
        db: Active async database session.
        login: E-mail address to look up.

    Returns:
        The matching :class:`~app.models.user.User`, or ``None`` if not found.
    """
    result = await db.execute(select(User).where(User.login == login))
    return result.scalar_one_or_none()


async def get_users(db: AsyncSession) -> list[User]:
    """Retrieve all user records.

    Args:
        db: Active async database session.

    Returns:
        A list of all :class:`~app.models.user.User` ORM instances.
    """
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def lock_user(db: AsyncSession, lock_ttl_seconds: int) -> User | None:
    """Atomically acquire the first available (unlocked or expired) user.

    Uses ``SELECT FOR UPDATE SKIP LOCKED`` so concurrent callers never
    receive the same account.

    Args:
        db: Active async database session.
        lock_ttl_seconds: Seconds after which a lock is considered expired
            and the account becomes available again.

    Returns:
        The locked :class:`~app.models.user.User`, or ``None`` if every
        account is currently held.
    """
    expiry = datetime.now(timezone.utc) - timedelta(seconds=lock_ttl_seconds)

    stmt = (
        select(User)
        .where(
            (User.locktime.is_(None)) | (User.locktime < expiry)
        )
        .order_by(User.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return None

    user.locktime = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(user)
    return user


async def free_users(db: AsyncSession) -> int:
    """Release all locked user accounts by setting their locktime to NULL.

    Args:
        db: Active async database session.

    Returns:
        The number of accounts that were unlocked.
    """
    stmt = (
        update(User)
        .where(User.locktime.is_not(None))
        .values(locktime=None)
    )
    result = await db.execute(stmt)
    rowcount: int = result.rowcount  # type: ignore[attr-defined]
    return rowcount
