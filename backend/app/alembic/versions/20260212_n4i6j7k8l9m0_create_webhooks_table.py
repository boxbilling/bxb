"""create webhooks table

Revision ID: n4i6j7k8l9m0
Revises: m3h5i6j7k8l9
Create Date: 2026-02-12 00:00:13.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "n4i6j7k8l9m0"
down_revision = "m3h5i6j7k8l9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("webhook_endpoint_id", sa.String(length=36), nullable=False),
        sa.Column("webhook_type", sa.String(length=100), nullable=False),
        sa.Column("object_type", sa.String(length=50), nullable=True),
        sa.Column("object_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_retried_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["webhook_endpoint_id"],
            ["webhook_endpoints.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_webhooks_webhook_endpoint_id", "webhooks", ["webhook_endpoint_id"]
    )
    op.create_index("ix_webhooks_webhook_type", "webhooks", ["webhook_type"])
    op.create_index("ix_webhooks_status", "webhooks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_webhooks_status", table_name="webhooks")
    op.drop_index("ix_webhooks_webhook_type", table_name="webhooks")
    op.drop_index("ix_webhooks_webhook_endpoint_id", table_name="webhooks")
    op.drop_table("webhooks")
