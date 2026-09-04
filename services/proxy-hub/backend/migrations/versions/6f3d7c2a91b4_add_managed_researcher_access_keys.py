"""add managed researcher access keys

Revision ID: 6f3d7c2a91b4
Revises: 2b734c8dd831
Create Date: 2026-09-03 08:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6f3d7c2a91b4"
down_revision: str | Sequence[str] | None = "2b734c8dd831"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the migration."""
    with op.batch_alter_table("principals") as batch_op:
        batch_op.add_column(
            sa.Column(
                "kind",
                sa.String(length=32),
                server_default="oidc_operator",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_principal_kind",
            "kind IN ('oidc_operator', 'managed_researcher')",
        )

    op.create_table(
        "access_keys",
        sa.Column("id", sa.String(length=48), nullable=False),
        sa.Column("token_digest", sa.String(length=128), nullable=False),
        sa.Column("token_prefix", sa.String(length=32), nullable=False),
        sa.Column("token_last_four", sa.String(length=4), nullable=False),
        sa.Column("principal_id", sa.String(length=48), nullable=False),
        sa.Column("tenant_id", sa.String(length=48), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("allowed_tools", sa.JSON(), nullable=False),
        sa.Column("request_limit", sa.Integer(), nullable=True),
        sa.Column("period_seconds", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_principal_id", sa.String(length=48), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_principal_id", sa.String(length=48), nullable=True),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(request_limit IS NULL AND period_seconds IS NULL) OR "
            "(request_limit > 0 AND period_seconds > 0)",
            name="ck_access_key_quota_pair",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_principal_id"],
            ["principals.id"],
        ),
        sa.ForeignKeyConstraint(["principal_id"], ["principals.id"]),
        sa.ForeignKeyConstraint(
            ["revoked_by_principal_id"],
            ["principals.id"],
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        op.f("ix_access_keys_expires_at"),
        "access_keys",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_keys_principal_id"),
        "access_keys",
        ["principal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_keys_tenant_id"),
        "access_keys",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "access_key_usage_windows",
        sa.Column("access_key_id", sa.String(length=48), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_seconds", sa.Integer(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["access_key_id"], ["access_keys.id"]),
        sa.PrimaryKeyConstraint(
            "access_key_id",
            "window_start",
            "period_seconds",
        ),
    )

    with op.batch_alter_table("mcp_session_affinities") as batch_op:
        batch_op.alter_column(
            "capability_id",
            existing_type=sa.String(length=48),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column("access_key_id", sa.String(length=48), nullable=True)
        )
        batch_op.create_index(
            op.f("ix_mcp_session_affinities_access_key_id"),
            ["access_key_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_mcp_session_affinities_access_key",
            "access_keys",
            ["access_key_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_mcp_affinity_credential",
            "(capability_id IS NOT NULL AND access_key_id IS NULL) OR "
            "(capability_id IS NULL AND access_key_id IS NOT NULL)",
        )

    op.add_column(
        "audit_events",
        sa.Column("access_key_id", sa.String(length=48), nullable=True),
    )
    op.create_index(
        op.f("ix_audit_events_access_key_id"),
        "audit_events",
        ["access_key_id"],
        unique=False,
    )


def downgrade() -> None:
    """Revert the migration."""
    op.drop_index(
        op.f("ix_audit_events_access_key_id"),
        table_name="audit_events",
    )
    op.drop_column("audit_events", "access_key_id")

    with op.batch_alter_table("mcp_session_affinities") as batch_op:
        batch_op.drop_constraint(
            "ck_mcp_affinity_credential",
            type_="check",
        )
        batch_op.drop_constraint(
            "fk_mcp_session_affinities_access_key",
            type_="foreignkey",
        )
        batch_op.drop_index(
            op.f("ix_mcp_session_affinities_access_key_id")
        )
        batch_op.drop_column("access_key_id")
        batch_op.alter_column(
            "capability_id",
            existing_type=sa.String(length=48),
            nullable=False,
        )

    op.drop_table("access_key_usage_windows")
    op.drop_index(op.f("ix_access_keys_tenant_id"), table_name="access_keys")
    op.drop_index(
        op.f("ix_access_keys_principal_id"),
        table_name="access_keys",
    )
    op.drop_index(op.f("ix_access_keys_expires_at"), table_name="access_keys")
    op.drop_table("access_keys")

    with op.batch_alter_table("principals") as batch_op:
        batch_op.drop_constraint("ck_principal_kind", type_="check")
        batch_op.drop_column("kind")
