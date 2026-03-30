"""Authentication endpoints: JWT token issuance."""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import Token
from app.services import botfarm as service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token, summary="Obtain JWT access token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Issue a JWT access token for valid credentials.

    Args:
        form_data: OAuth2 form containing ``username`` (login e-mail) and
            ``password``.
        db: Injected async database session.

    Returns:
        :class:`~app.schemas.auth.Token` with a signed JWT and
        ``token_type="bearer"``.

    Raises:
        HTTPException: 401 if the credentials are incorrect.
    """
    return await service.login(db, form_data.username, form_data.password)
