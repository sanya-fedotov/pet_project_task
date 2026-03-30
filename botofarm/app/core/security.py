"""Password hashing and JWT token utilities."""

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Re-export so callers can catch the standard PyJWT error without importing
# jwt directly.
PyJWTError = jwt.PyJWTError


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        plain: The plain-text password to hash.

    Returns:
        A bcrypt-hashed string safe to store in the database.
    """
    return str(_pwd_context.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash.

    Args:
        plain: The plain-text password provided by the user.
        hashed: The bcrypt hash stored in the database.

    Returns:
        ``True`` if the password matches, ``False`` otherwise.
    """
    return bool(_pwd_context.verify(plain, hashed))


def create_access_token(
    data: dict[str, object],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload to encode into the token (typically ``{"sub": login}``).
        expires_delta: Custom token lifetime.  Defaults to
            ``ACCESS_TOKEN_EXPIRE_MINUTES`` from settings.

    Returns:
        A signed JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    """Decode and validate a JWT access token.

    Args:
        token: The encoded JWT string.

    Returns:
        The decoded payload as a plain dictionary.

    Raises:
        jwt.PyJWTError: If the token is invalid or has expired.
    """
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "PyJWTError",
]
