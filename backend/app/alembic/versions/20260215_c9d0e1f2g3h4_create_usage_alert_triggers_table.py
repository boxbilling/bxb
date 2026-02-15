"""create usage alert triggers table

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-02-15 22:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c9d0e1f2g3h4"
down_revision = "b8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_alert_triggers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("usage_alert_id", sa.String(length=36), nullable=False),
        sa.Column("current_usage", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("threshold_value", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("metric_code", sa.String(length=255), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["usage_alert_id"],
            ["usage_alerts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_usage_alert_triggers_usage_alert_id",
        "usage_alert_triggers",
        ["usage_alert_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_usage_alert_triggers_usage_alert_id",
        table_name="usage_alert_triggers",
    )
    op.drop_table("usage_alert_triggers")
