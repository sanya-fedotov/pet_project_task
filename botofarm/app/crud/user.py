"""Data-access layer: all direct database interactions for the User model."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import DomainType, EnvType, User
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


async def get_users(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[User]:
    """Retrieve user records with optional pagination.

    Args:
        db: Active async database session.
        limit: Maximum number of records to return. Defaults to 100.
        offset: Number of records to skip before returning results.
            Defaults to 0.

    Returns:
        A list of :class:`~app.models.user.User` ORM instances.
    """
    result = await db.execute(
        select(User).order_by(User.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def lock_user(
    db: AsyncSession,
    lock_ttl_seconds: int,
    project_id: uuid.UUID | None = None,
    env: EnvType | None = None,
    domain: DomainType | None = None,
) -> User | None:
    """Atomically acquire the first available (unlocked or expired) user.

    Uses ``SELECT FOR UPDATE SKIP LOCKED`` so concurrent callers never
    receive the same account.

    Args:
        db: Active async database session.
        lock_ttl_seconds: Seconds after which a lock is considered expired
            and the account becomes available again.
        project_id: When provided, restrict the search to this project.
        env: When provided, restrict the search to this environment.
        domain: When provided, restrict the search to this domain.

    Returns:
        The locked :class:`~app.models.user.User`, or ``None`` if every
        matching account is currently held.
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
    if project_id is not None:
        stmt = stmt.where(User.project_id == project_id)
    if env is not None:
        stmt = stmt.where(User.env == env)
    if domain is not None:
        stmt = stmt.where(User.domain == domain)

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return None

    user.locktime = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(user)
    return user


async def free_users(
    db: AsyncSession,
    project_id: uuid.UUID | None = None,
) -> int:
    """Release locked user accounts by setting their locktime to NULL.

    Args:
        db: Active async database session.
        project_id: When provided, only accounts belonging to this project
            are released.  When ``None``, all locked accounts are released.

    Returns:
        The number of accounts that were unlocked.
    """
    stmt = update(User).where(User.locktime.is_not(None)).values(locktime=None)
    if project_id is not None:
        stmt = stmt.where(User.project_id == project_id)
    result = await db.execute(stmt)
    rowcount: int = result.rowcount  # type: ignore[attr-defined]
    return rowcount
