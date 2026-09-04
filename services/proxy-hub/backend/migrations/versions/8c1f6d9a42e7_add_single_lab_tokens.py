"""add single-lab Token facade state

Revision ID: 8c1f6d9a42e7
Revises: 6f3d7c2a91b4
Create Date: 2026-09-04 03:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c1f6d9a42e7"
down_revision: str | Sequence[str] | None = "6f3d7c2a91b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _allow_expired_audit_deletion() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER audit_events_reject_delete ON audit_events")
        op.execute(
            """
            CREATE FUNCTION reject_recent_audit_event_delete()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.occurred_at >= CURRENT_TIMESTAMP - INTERVAL '180 days' THEN
                    RAISE EXCEPTION 'recent audit events are append-only';
                END IF;
                RETURN OLD;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_reject_delete
            BEFORE DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_recent_audit_event_delete()
            """
        )
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER audit_events_reject_delete")
        op.execute(
            """
            CREATE TRIGGER audit_events_reject_delete
            BEFORE DELETE ON audit_events
            WHEN OLD.occurred_at >= datetime('now', '-180 days')
            BEGIN
                SELECT RAISE(ABORT, 'recent audit events are append-only');
            END
            """
        )


def _restore_append_only_audit() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER audit_events_reject_delete ON audit_events")
        op.execute("DROP FUNCTION reject_recent_audit_event_delete()")
        op.execute(
            """
            CREATE TRIGGER audit_events_reject_delete
            BEFORE DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation()
            """
        )
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER audit_events_reject_delete")
        op.execute(
            """
            CREATE TRIGGER audit_events_reject_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit events are append-only');
            END
            """
        )


def upgrade() -> None:
    """Apply the migration."""
    with op.batch_alter_table("principals") as batch_op:
        batch_op.add_column(
            sa.Column("managed_name_key", sa.String(length=256), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_principals_managed_name_key",
            ["managed_name_key"],
        )

    with op.batch_alter_table("access_keys") as batch_op:
        batch_op.add_column(
            sa.Column("token_name_key", sa.String(length=256), nullable=True)
        )
        batch_op.add_column(
            sa.Column("active_name_key", sa.String(length=256), nullable=True)
        )
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
        batch_op.create_unique_constraint(
            "uq_access_keys_active_name_key",
            ["active_name_key"],
        )
        batch_op.create_index(
            op.f("ix_access_keys_token_name_key"),
            ["token_name_key"],
            unique=False,
        )

    _allow_expired_audit_deletion()


def downgrade() -> None:
    """Revert the migration."""
    _restore_append_only_audit()
    op.execute(
        sa.text(
            "UPDATE access_keys SET expires_at = CURRENT_TIMESTAMP "
            "WHERE expires_at IS NULL"
        )
    )
    with op.batch_alter_table("access_keys") as batch_op:
        batch_op.drop_index(op.f("ix_access_keys_token_name_key"))
        batch_op.drop_constraint(
            "uq_access_keys_active_name_key",
            type_="unique",
        )
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.drop_column("active_name_key")
        batch_op.drop_column("token_name_key")

    with op.batch_alter_table("principals") as batch_op:
        batch_op.drop_constraint(
            "uq_principals_managed_name_key",
            type_="unique",
        )
        batch_op.drop_column("managed_name_key")
