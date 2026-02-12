"""create wallets table

Revision ID: a1b2c3d4e5f7
Revises: c572a3f1d896
Create Date: 2026-02-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "c572a3f1d896"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("code", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("balance_cents", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
        sa.Column("credits_balance", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
        sa.Column("consumed_amount_cents", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
        sa.Column("consumed_credits", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0"),
        sa.Column("rate_amount", sa.Numeric(precision=12, scale=4), nullable=False, server_default="1"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("expiration_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "code", name="uq_wallets_customer_id_code"),
    )
    op.create_index("ix_wallets_customer_id", "wallets", ["customer_id"], unique=False)
    op.create_index("ix_wallets_status", "wallets", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wallets_status", table_name="wallets")
    op.drop_index("ix_wallets_customer_id", table_name="wallets")
    op.drop_table("wallets")
