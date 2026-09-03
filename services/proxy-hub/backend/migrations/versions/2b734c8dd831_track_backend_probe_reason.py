"""track backend probe reason

Revision ID: 2b734c8dd831
Revises: 4a4328e1b931
Create Date: 2026-09-03 04:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2b734c8dd831"
down_revision: str | Sequence[str] | None = "4a4328e1b931"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column(
        "scholar_backends",
        sa.Column("last_probe_reason", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column("scholar_backends", "last_probe_reason")
