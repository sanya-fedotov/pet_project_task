"""Pydantic schemas for User request and response payloads."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import DomainType, EnvType


class UserCreate(BaseModel):
    """Schema for creating a new bot account.

    Attributes:
        login: E-mail address used as the unique login.
        password: Plain-text password (will be hashed before storage).
        project_id: UUID of the owning project.
        env: Deployment environment.
        domain: Traffic domain.
    """

    login: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=72)]
    project_id: uuid.UUID
    env: EnvType
    domain: DomainType


class UserResponse(BaseModel):
    """Schema returned to callers — never exposes the password hash.

    Attributes:
        id: Unique identifier of the account.
        created_at: UTC creation timestamp.
        login: E-mail login of the account.
        project_id: UUID of the owning project.
        env: Deployment environment.
        domain: Traffic domain.
        locktime: UTC timestamp when the account was locked, or ``None``.
    """

    id: uuid.UUID
    created_at: datetime
    login: str
    project_id: uuid.UUID
    env: EnvType
    domain: DomainType
    locktime: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LockUserRequest(BaseModel):
    """Optional filters for selecting which account to lock.

    All fields are optional — when omitted, no filter is applied for
    that dimension.

    Attributes:
        project_id: Restrict the search to this project.
        env: Restrict the search to this deployment environment.
        domain: Restrict the search to this traffic domain.
    """

    project_id: uuid.UUID | None = None
    env: EnvType | None = None
    domain: DomainType | None = None


class FreeUsersRequest(BaseModel):
    """Optional filters for selecting which accounts to free.

    Attributes:
        project_id: When provided, only accounts belonging to this project
            are released.
    """

    project_id: uuid.UUID | None = None


class FreeUsersResponse(BaseModel):
    """Response payload for the free-users operation.

    Attributes:
        freed: Number of accounts that were unlocked.
    """

    freed: int
