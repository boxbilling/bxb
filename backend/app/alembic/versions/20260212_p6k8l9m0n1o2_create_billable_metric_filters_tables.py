"""create billable metric filters tables

Revision ID: p6k8l9m0n1o2
Revises: o5j7k8l9m0n1
Create Date: 2026-02-12 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "p6k8l9m0n1o2"
down_revision = "o5j7k8l9m0n1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create billable_metric_filters table
    op.create_table(
        "billable_metric_filters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("billable_metric_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
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
            ["billable_metric_id"],
            ["billable_metrics.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "billable_metric_id", "key", name="uq_billable_metric_filter_metric_key"
        ),
    )
    op.create_index(
        "ix_billable_metric_filters_billable_metric_id",
        "billable_metric_filters",
        ["billable_metric_id"],
    )
    op.create_index(
        "ix_billable_metric_filters_metric_key",
        "billable_metric_filters",
        ["billable_metric_id", "key"],
    )

    # Create charge_filters table
    op.create_table(
        "charge_filters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("charge_id", sa.String(length=36), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("invoice_display_name", sa.String(length=255), nullable=True),
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
            ["charge_id"],
            ["charges.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_charge_filters_charge_id",
        "charge_filters",
        ["charge_id"],
    )

    # Create charge_filter_values table
    op.create_table(
        "charge_filter_values",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("charge_filter_id", sa.String(length=36), nullable=False),
        sa.Column("billable_metric_filter_id", sa.String(length=36), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["charge_filter_id"],
            ["charge_filters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["billable_metric_filter_id"],
            ["billable_metric_filters.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "charge_filter_id",
            "billable_metric_filter_id",
            name="uq_charge_filter_value_filter_metric",
        ),
    )
    op.create_index(
        "ix_charge_filter_values_charge_filter_id",
        "charge_filter_values",
        ["charge_filter_id"],
    )
    op.create_index(
        "ix_charge_filter_values_billable_metric_filter_id",
        "charge_filter_values",
        ["billable_metric_filter_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_charge_filter_values_billable_metric_filter_id",
        table_name="charge_filter_values",
    )
    op.drop_index(
        "ix_charge_filter_values_charge_filter_id",
        table_name="charge_filter_values",
    )
    op.drop_table("charge_filter_values")

    op.drop_index("ix_charge_filters_charge_id", table_name="charge_filters")
    op.drop_table("charge_filters")

    op.drop_index(
        "ix_billable_metric_filters_metric_key",
        table_name="billable_metric_filters",
    )
    op.drop_index(
        "ix_billable_metric_filters_billable_metric_id",
        table_name="billable_metric_filters",
    )
    op.drop_table("billable_metric_filters")
