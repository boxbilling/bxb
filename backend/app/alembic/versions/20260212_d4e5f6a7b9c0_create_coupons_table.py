"""create coupons table

Revision ID: d4e5f6a7b9c0
Revises: c3d4e5f6a7b9
Create Date: 2026-02-12 00:00:03.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b9c0"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("coupon_type", sa.String(length=20), nullable=False),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("amount_currency", sa.String(length=3), nullable=True),
        sa.Column("percentage_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("frequency_duration", sa.Integer(), nullable=True),
        sa.Column("reusable", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "expiration",
            sa.String(length=20),
            nullable=False,
            server_default="no_expiration",
        ),
        sa.Column("expiration_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
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
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_coupons_code", "coupons", ["code"])
    op.create_index("ix_coupons_status", "coupons", ["status"])


def downgrade() -> None:
    op.drop_index("ix_coupons_status", table_name="coupons")
    op.drop_index("ix_coupons_code", table_name="coupons")
    op.drop_table("coupons")
