"""SQLAlchemy ORM model for the User entity."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EnvType(str, enum.Enum):
    """Deployment environment of a bot account."""

    prod = "prod"
    preprod = "preprod"
    stage = "stage"


class DomainType(str, enum.Enum):
    """Traffic domain of a bot account."""

    canary = "canary"
    regular = "regular"


class User(Base):
    """ORM model representing a bot account managed by the farm.

    Attributes:
        id: Unique identifier (UUID v4).
        created_at: UTC timestamp of record creation (immutable).
        login: E-mail address used as the unique login.
        password: bcrypt hash of the account password.
        project_id: UUID referencing the owning project.
        env: Deployment environment (prod / preprod / stage).
        domain: Traffic domain (canary / regular).
        locktime: UTC timestamp when the account was last locked; ``None``
            means the account is free.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    login: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    env: Mapped[EnvType] = mapped_column(
        Enum(EnvType, name="envtype"),
        nullable=False,
    )
    domain: Mapped[DomainType] = mapped_column(
        Enum(DomainType, name="domaintype"),
        nullable=False,
    )
    locktime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )
