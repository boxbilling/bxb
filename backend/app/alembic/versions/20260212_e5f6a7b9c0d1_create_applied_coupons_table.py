"""create applied_coupons table

Revision ID: e5f6a7b9c0d1
Revises: d4e5f6a7b9c0
Create Date: 2026-02-12 00:00:04.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b9c0d1"
down_revision = "d4e5f6a7b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applied_coupons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("coupon_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("amount_currency", sa.String(length=3), nullable=True),
        sa.Column("percentage_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("frequency_duration", sa.Integer(), nullable=True),
        sa.Column("frequency_duration_remaining", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_applied_coupons_coupon_id", "applied_coupons", ["coupon_id"])
    op.create_index("ix_applied_coupons_customer_id", "applied_coupons", ["customer_id"])
    op.create_index("ix_applied_coupons_status", "applied_coupons", ["status"])


def downgrade() -> None:
    op.drop_index("ix_applied_coupons_status", table_name="applied_coupons")
    op.drop_index("ix_applied_coupons_customer_id", table_name="applied_coupons")
    op.drop_index("ix_applied_coupons_coupon_id", table_name="applied_coupons")
    op.drop_table("applied_coupons")
