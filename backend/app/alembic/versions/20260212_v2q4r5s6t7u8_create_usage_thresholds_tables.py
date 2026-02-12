"""create usage_thresholds and applied_usage_thresholds tables

Revision ID: v2q4r5s6t7u8
Revises: u1p3q4r5s6t7
Create Date: 2026-02-12 21:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "v2q4r5s6t7u8"
down_revision = "u1p3q4r5s6t7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create usage_thresholds table
    op.create_table(
        "usage_thresholds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("subscription_id", sa.String(length=36), nullable=True),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), nullable=False, server_default="USD"
        ),
        sa.Column("recurring", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("threshold_display_name", sa.String(length=255), nullable=True),
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
            ["organization_id"],
            ["organizations.id"],
            name="fk_usage_thresholds_organization_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name="fk_usage_thresholds_plan_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name="fk_usage_thresholds_subscription_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "(plan_id IS NOT NULL AND subscription_id IS NULL) OR "
            "(plan_id IS NULL AND subscription_id IS NOT NULL)",
            name="ck_usage_thresholds_exactly_one_parent",
        ),
    )
    op.create_index(
        "ix_usage_thresholds_organization_id",
        "usage_thresholds",
        ["organization_id"],
    )
    op.create_index("ix_usage_thresholds_plan_id", "usage_thresholds", ["plan_id"])
    op.create_index(
        "ix_usage_thresholds_subscription_id",
        "usage_thresholds",
        ["subscription_id"],
    )

    # Create applied_usage_thresholds table
    op.create_table(
        "applied_usage_thresholds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("usage_threshold_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=True),
        sa.Column("crossed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "lifetime_usage_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_applied_usage_thresholds_organization_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["usage_threshold_id"],
            ["usage_thresholds.id"],
            name="fk_applied_usage_thresholds_threshold_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name="fk_applied_usage_thresholds_subscription_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_applied_usage_thresholds_invoice_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_applied_usage_thresholds_organization_id",
        "applied_usage_thresholds",
        ["organization_id"],
    )
    op.create_index(
        "ix_applied_usage_thresholds_threshold_id",
        "applied_usage_thresholds",
        ["usage_threshold_id"],
    )
    op.create_index(
        "ix_applied_usage_thresholds_subscription_id",
        "applied_usage_thresholds",
        ["subscription_id"],
    )
    op.create_index(
        "ix_applied_usage_thresholds_invoice_id",
        "applied_usage_thresholds",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_applied_usage_thresholds_invoice_id",
        table_name="applied_usage_thresholds",
    )
    op.drop_index(
        "ix_applied_usage_thresholds_subscription_id",
        table_name="applied_usage_thresholds",
    )
    op.drop_index(
        "ix_applied_usage_thresholds_threshold_id",
        table_name="applied_usage_thresholds",
    )
    op.drop_index(
        "ix_applied_usage_thresholds_organization_id",
        table_name="applied_usage_thresholds",
    )
    op.drop_table("applied_usage_thresholds")
    op.drop_index(
        "ix_usage_thresholds_subscription_id", table_name="usage_thresholds"
    )
    op.drop_index("ix_usage_thresholds_plan_id", table_name="usage_thresholds")
    op.drop_index(
        "ix_usage_thresholds_organization_id", table_name="usage_thresholds"
    )
    op.drop_table("usage_thresholds")
