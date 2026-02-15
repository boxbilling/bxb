"""create usage alerts table

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-02-15 20:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_alerts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("billable_metric_id", sa.String(length=36), nullable=False),
        sa.Column("threshold_value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("times_triggered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["billable_metric_id"],
            ["billable_metrics.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_alerts_organization_id",
        "usage_alerts",
        ["organization_id"],
    )
    op.create_index(
        "ix_usage_alerts_subscription_id",
        "usage_alerts",
        ["subscription_id"],
    )
    op.create_index(
        "ix_usage_alerts_billable_metric_id",
        "usage_alerts",
        ["billable_metric_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_alerts_billable_metric_id", table_name="usage_alerts")
    op.drop_index("ix_usage_alerts_subscription_id", table_name="usage_alerts")
    op.drop_index("ix_usage_alerts_organization_id", table_name="usage_alerts")
    op.drop_table("usage_alerts")
