"""Shared API dependencies: authentication helpers used across routers."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import PyJWTError, decode_access_token
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that resolves the current authenticated user from a JWT.

    Args:
        token: Bearer token extracted from the ``Authorization`` header.
        db: Injected async database session.

    Returns:
        The authenticated :class:`~app.models.user.User` ORM instance.

    Raises:
        HTTPException: 401 if the token is invalid or the user no longer
            exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        raw_sub = payload.get("sub")
        if not isinstance(raw_sub, str):
            raise credentials_exception
        token_data = TokenData(sub=raw_sub)
    except PyJWTError as exc:
        raise credentials_exception from exc

    user = await user_crud.get_user_by_login(db, token_data.sub)
    if user is None:
        raise credentials_exception
    return user
