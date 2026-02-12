"""create applied_add_ons table

Revision ID: g7b9c0d1e2f3
Revises: f6a7b9c0d1e2
Create Date: 2026-02-12 00:00:06.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "g7b9c0d1e2f3"
down_revision = "f6a7b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applied_add_ons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("add_on_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("amount_currency", sa.String(length=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.ForeignKeyConstraint(["add_on_id"], ["add_ons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_applied_add_ons_add_on_id", "applied_add_ons", ["add_on_id"])
    op.create_index("ix_applied_add_ons_customer_id", "applied_add_ons", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_applied_add_ons_customer_id", table_name="applied_add_ons")
    op.drop_index("ix_applied_add_ons_add_on_id", table_name="applied_add_ons")
    op.drop_table("applied_add_ons")
