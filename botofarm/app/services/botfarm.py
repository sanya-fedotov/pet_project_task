"""Business-logic layer for the bot-farm service.

All orchestration between the security utilities and the data-access layer
lives here.  API handlers must never call CRUD functions directly.
"""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.crud import user as user_crud
from app.schemas.auth import Token
from app.schemas.user import FreeUsersResponse, UserCreate, UserResponse


async def login(db: AsyncSession, username: str, password: str) -> Token:
    """Authenticate a user and return a signed JWT access token.

    Args:
        db: Active async database session.
        username: The user's login e-mail (OAuth2 ``username`` field).
        password: The plain-text password to verify.

    Returns:
        :class:`~app.schemas.auth.Token` with a signed JWT and
        ``token_type="bearer"``.

    Raises:
        HTTPException: 401 if the credentials are incorrect or the user does
            not exist.
    """
    user = await user_crud.get_user_by_login(db, username)
    if user is None or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect login or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.login})
    return Token(access_token=access_token, token_type="bearer")


async def create_user(db: AsyncSession, schema: UserCreate) -> UserResponse:
    """Create a new bot account with a hashed password.

    Args:
        db: Active async database session.
        schema: Validated creation payload from the API layer.

    Returns:
        :class:`~app.schemas.user.UserResponse` for the created account.

    Raises:
        HTTPException: 409 if the e-mail login is already registered.
    """
    hashed = hash_password(schema.password)
    try:
        user = await user_crud.create_user(db, schema, hashed)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this login already exists.",
        ) from exc
    return UserResponse.model_validate(user)


async def get_users(db: AsyncSession) -> list[UserResponse]:
    """Return all bot accounts.

    Args:
        db: Active async database session.

    Returns:
        A list of :class:`~app.schemas.user.UserResponse` objects.
    """
    users = await user_crud.get_users(db)
    return [UserResponse.model_validate(u) for u in users]


async def lock_user(db: AsyncSession) -> UserResponse:
    """Acquire the first free (or expired) bot account.

    Args:
        db: Active async database session.

    Returns:
        :class:`~app.schemas.user.UserResponse` for the newly locked account.

    Raises:
        HTTPException: 404 if no free accounts are available.
    """
    user = await user_crud.lock_user(db, settings.lock_ttl_seconds)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No free users available.",
        )
    return UserResponse.model_validate(user)


async def free_users(db: AsyncSession) -> FreeUsersResponse:
    """Release all locked bot accounts.

    Args:
        db: Active async database session.

    Returns:
        :class:`~app.schemas.user.FreeUsersResponse` containing the count of
        accounts that were unlocked.
    """
    count = await user_crud.free_users(db)
    return FreeUsersResponse(freed=count)
