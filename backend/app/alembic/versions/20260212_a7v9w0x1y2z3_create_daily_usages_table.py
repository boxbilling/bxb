"""create daily_usages table

Revision ID: a7v9w0x1y2z3
Revises: z6u8v9w0x1y2
Create Date: 2026-02-12 23:55:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a7v9w0x1y2z3"
down_revision = "z6u8v9w0x1y2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daily_usages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("billable_metric_id", sa.String(length=36), nullable=False),
        sa.Column("external_customer_id", sa.String(length=255), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column(
            "usage_value", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"
        ),
        sa.Column("events_count", sa.Integer(), nullable=False, server_default="0"),
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
            ["subscription_id"], ["subscriptions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["billable_metric_id"], ["billable_metrics.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "billable_metric_id",
            "usage_date",
            name="uq_daily_usage_sub_metric_date",
        ),
    )
    op.create_index(
        "ix_daily_usages_subscription_id", "daily_usages", ["subscription_id"]
    )
    op.create_index(
        "ix_daily_usages_billable_metric_id", "daily_usages", ["billable_metric_id"]
    )
    op.create_index(
        "ix_daily_usages_sub_metric_date",
        "daily_usages",
        ["subscription_id", "billable_metric_id", "usage_date"],
    )


def downgrade():
    op.drop_index("ix_daily_usages_sub_metric_date", table_name="daily_usages")
    op.drop_index("ix_daily_usages_billable_metric_id", table_name="daily_usages")
    op.drop_index("ix_daily_usages_subscription_id", table_name="daily_usages")
    op.drop_table("daily_usages")
