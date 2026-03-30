"""create users table

Revision ID: 0001
Revises:
Create Date: 2026-03-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the users table with all required columns and constraints."""
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("login", sa.String(255), nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "env",
            sa.Enum("prod", "preprod", "stage", name="envtype"),
            nullable=False,
        ),
        sa.Column(
            "domain",
            sa.Enum("canary", "regular", name="domaintype"),
            nullable=False,
        ),
        sa.Column(
            "locktime",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_users_login", "users", ["login"], unique=True)
    op.create_index("ix_users_locktime", "users", ["locktime"], unique=False)


def downgrade() -> None:
    """Drop the users table and associated enum types."""
    op.drop_index("ix_users_locktime", table_name="users")
    op.drop_index("ix_users_login", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS envtype")
    op.execute("DROP TYPE IF EXISTS domaintype")
