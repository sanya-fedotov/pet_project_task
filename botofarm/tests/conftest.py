"""Shared pytest fixtures for the botofarm test suite.

Two database back-ends are provided:

* **SQLite (in-memory)** — fast, used by unit tests and most API tests that
  do not exercise row-level locking (``db_session`` / ``async_client``).
* **PostgreSQL (testcontainers)** — real Postgres instance, used for
  integration tests that need ``SELECT FOR UPDATE SKIP LOCKED``
  (``pg_db_session`` / ``pg_async_client``).
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import DomainType, EnvType, User

# ---------------------------------------------------------------------------
# SQLite — fast fixtures for unit and non-locking API tests
# ---------------------------------------------------------------------------
_SQLITE_URL = "sqlite+aiosqlite:///:memory:"

_sqlite_engine = create_async_engine(
    _SQLITE_URL,
    connect_args={"check_same_thread": False},
)
_sqlite_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_sqlite_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_tables() -> AsyncGenerator[None, None]:
    """Create all SQLite tables once per test session and drop them afterwards."""
    async with _sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional SQLite test session rolled back after each test.

    Using a nested transaction (SAVEPOINT) keeps each test isolated without
    recreating the schema.
    """
    async with _sqlite_session_factory() as session:
        await session.begin_nested()
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an :class:`httpx.AsyncClient` wired to the SQLite test database.

    The ``get_db`` dependency is overridden so that every request uses the
    same rolled-back session as the test.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def test_user(db_session: AsyncSession) -> User:
    """Persist a single test user and return the ORM instance.

    The user's plain-text password is ``"testpassword"``.
    """
    user = User(
        id=uuid.uuid4(),
        login="testuser@example.com",
        password=hash_password("testpassword"),
        project_id=uuid.uuid4(),
        env=EnvType.prod,
        domain=DomainType.regular,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """Return Authorization headers carrying a valid JWT for ``test_user``."""
    token = create_access_token(data={"sub": test_user.login})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# PostgreSQL (testcontainers) — fixtures for lock-path integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container():
    """Start a throwaway PostgreSQL container for the test session.

    Yields:
        The running :class:`~testcontainers.postgres.PostgresContainer`.
    """
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest_asyncio.fixture(scope="session")
async def pg_engine(pg_container):
    """Create an async SQLAlchemy engine connected to the test container.

    Args:
        pg_container: Running Postgres testcontainer.

    Yields:
        An :class:`~sqlalchemy.ext.asyncio.AsyncEngine` with all tables
        created.
    """
    # testcontainers returns a psycopg2-style URL; swap driver to asyncpg.
    sync_url: str = pg_container.get_connection_url()
    async_url = (
        sync_url
        .replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        .replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    engine = create_async_engine(async_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def pg_db_session(pg_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a PostgreSQL session rolled back after each test.

    Args:
        pg_engine: Session-scoped async engine.

    Yields:
        An :class:`~sqlalchemy.ext.asyncio.AsyncSession` using a SAVEPOINT
        so each test is isolated.
    """
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with factory() as session:
        await session.begin_nested()
        yield session
        await session.rollback()


@pytest_asyncio.fixture()
async def pg_async_client(
    pg_db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Yield an :class:`httpx.AsyncClient` wired to the PostgreSQL test DB.

    Args:
        pg_db_session: PostgreSQL session with SAVEPOINT isolation.

    Yields:
        Configured async HTTP client.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield pg_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def pg_test_user(pg_db_session: AsyncSession) -> User:
    """Persist a single test user in PostgreSQL and return the ORM instance.

    The user's plain-text password is ``"testpassword"``.
    """
    user = User(
        id=uuid.uuid4(),
        login="pg-testuser@example.com",
        password=hash_password("testpassword"),
        project_id=uuid.uuid4(),
        env=EnvType.prod,
        domain=DomainType.regular,
    )
    pg_db_session.add(user)
    await pg_db_session.flush()
    await pg_db_session.refresh(user)
    return user


@pytest.fixture()
def pg_auth_headers(pg_test_user: User) -> dict[str, str]:
    """Return Authorization headers carrying a valid JWT for ``pg_test_user``."""
    token = create_access_token(data={"sub": pg_test_user.login})
    return {"Authorization": f"Bearer {token}"}
