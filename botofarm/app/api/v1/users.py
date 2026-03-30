"""User management endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import FreeUsersResponse, UserCreate, UserResponse
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
    summary="List all bot accounts",
)
async def get_users(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[UserResponse]:
    """Return a list of all bot accounts.

    Args:
        db: Injected async database session.
        _current_user: Authenticated caller (required — not used directly).

    Returns:
        List of :class:`~app.schemas.user.UserResponse` objects.
    """
    return await botfarm_service.get_users(db)


@router.post(
    "/lock",
    response_model=UserResponse,
    summary="Lock (acquire) a free bot account",
)
async def lock_user(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Atomically acquire the first free or expired bot account.

    Args:
        db: Injected async database session.
        _current_user: Authenticated caller (required — not used directly).

    Returns:
        :class:`~app.schemas.user.UserResponse` for the locked account.

    Raises:
        HTTPException: 404 if no free accounts are available.
    """
    return await botfarm_service.lock_user(db)


@router.post(
    "/free",
    response_model=FreeUsersResponse,
    summary="Release all locked bot accounts",
)
async def free_users(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> FreeUsersResponse:
    """Set locktime to NULL for every locked account.

    Args:
        db: Injected async database session.
        _current_user: Authenticated caller (required — not used directly).

    Returns:
        :class:`~app.schemas.user.FreeUsersResponse` with the count of
        released accounts.
    """
    return await botfarm_service.free_users(db)
