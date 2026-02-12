"""add progressive billing fields to invoices

Revision ID: w3r5s6t7u8v9
Revises: v2q4r5s6t7u8
Create Date: 2026-02-12 22:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "w3r5s6t7u8v9"
down_revision = "v2q4r5s6t7u8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "invoice_type",
            sa.String(length=30),
            nullable=False,
            server_default="subscription",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "progressive_billing_credit_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "progressive_billing_credit_amount_cents")
    op.drop_column("invoices", "invoice_type")
