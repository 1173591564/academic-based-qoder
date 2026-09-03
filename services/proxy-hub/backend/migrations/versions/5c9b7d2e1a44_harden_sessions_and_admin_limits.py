"""Harden capability revocation and administration limits.

Revision ID: 5c9b7d2e1a44
Revises: 2b734c8dd831
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c9b7d2e1a44"
down_revision: str | None = "2b734c8dd831"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add capability versions and database-backed admin rate limits."""
    with op.batch_alter_table("dsh_capabilities") as batch:
        batch.add_column(
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
    op.create_table(
        "admin_rate_limits",
        sa.Column("session_id", sa.String(length=96), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "request_count > 0",
            name="ck_admin_rate_limit_request_count",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["browser_sessions.id"],
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )


def downgrade() -> None:
    """Remove administration limits and capability versions."""
    op.drop_table("admin_rate_limits")
    with op.batch_alter_table("dsh_capabilities") as batch:
        batch.drop_column("version")
