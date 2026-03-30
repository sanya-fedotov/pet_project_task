"""User management endpoints."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import (
    FreeUsersRequest,
    FreeUsersResponse,
    LockUserRequest,
    UserCreate,
    UserResponse,
)
from app.services import botfarm as botfarm_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bot account",
)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Register a new bot account in the farm.

    Args:
        user_data: Validated creation payload.
        db: Injected async database session.
        _current_user: Authenticated caller (required — not used directly).

    Returns:
        :class:`~app.schemas.user.UserResponse` for the created account.

    Raises:
        HTTPException: 409 if the login is already taken.
    """
    return await botfarm_service.create_user(db, user_data)


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List bot accounts",
)
async def get_users(
    limit: int = Query(default=100, ge=1, le=1000, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[UserResponse]:
    """Return a paginated list of bot accounts.

    Args:
        limit: Maximum number of accounts to return (1–1000). Defaults to 100.
        offset: Number of accounts to skip. Defaults to 0.
        db: Injected async database session.
        _current_user: Authenticated caller (required — not used directly).

    Returns:
        List of :class:`~app.schemas.user.UserResponse` objects.
    """
    return await botfarm_service.get_users(db, limit=limit, offset=offset)


@router.post(
    "/lock",
    response_model=UserResponse,
    summary="Lock (acquire) a free bot account",
)
async def lock_user(
    filters: LockUserRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Atomically acquire the first free or expired bot account.

    Optionally filters by project, environment, and domain so that test
    runs targeting specific segments never steal accounts from other segments.

    Args:
        filters: Optional project/env/domain constraints.
        db: Injected async database session.
        _current_user: Authenticated caller (required — not used directly).

    Returns:
        :class:`~app.schemas.user.UserResponse` for the locked account.

    Raises:
        HTTPException: 404 if no matching free accounts are available.
    """
    return await botfarm_service.lock_user(db, filters)


@router.post(
    "/free",
    response_model=FreeUsersResponse,
    summary="Release locked bot accounts",
)
async def free_users(
    filters: FreeUsersRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> FreeUsersResponse:
    """Set locktime to NULL for locked accounts, optionally scoped to a project.

    Args:
        filters: Optional project constraint; omit to release all locked accounts.
        db: Injected async database session.
        _current_user: Authenticated caller (required — not used directly).

    Returns:
        :class:`~app.schemas.user.FreeUsersResponse` with the count of
        released accounts.
    """
    return await botfarm_service.free_users(db, filters)
