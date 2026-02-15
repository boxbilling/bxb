"""Create integration_sync_history table.

Revision ID: f9898f4e89a3
Revises: a7b8c9d0e1f2
Create Date: 2026-02-15
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision = "f9898f4e89a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_sync_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "integration_id",
            sa.String(length=36),
            sa.ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("integration_sync_history")
