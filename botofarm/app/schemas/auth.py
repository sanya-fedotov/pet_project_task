"""Pydantic schemas for authentication request and response payloads."""

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """OAuth2 token response payload.

    Attributes:
        access_token: Signed JWT string.
        token_type: Always ``"bearer"``.
    """

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Decoded payload extracted from a JWT token.

    Attributes:
        sub: Subject claim — the user's login (e-mail address).
    """

    sub: EmailStr
