"""rename monetary fields to add _cents suffix

Revision ID: c1aef6cad7d1
Revises: h4i5j6k7l8m9
Create Date: 2026-02-27

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c1aef6cad7d1"
down_revision = "h4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename Invoice monetary columns
    op.alter_column("invoices", "subtotal", new_column_name="subtotal_cents")
    op.alter_column("invoices", "tax_amount", new_column_name="tax_amount_cents")
    op.alter_column("invoices", "total", new_column_name="total_cents")
    op.alter_column("invoices", "prepaid_credit_amount", new_column_name="prepaid_credit_amount_cents")

    # Rename Payment monetary column
    op.alter_column("payments", "amount", new_column_name="amount_cents")


def downgrade() -> None:
    # Revert Payment monetary column
    op.alter_column("payments", "amount_cents", new_column_name="amount")

    # Revert Invoice monetary columns
    op.alter_column("invoices", "prepaid_credit_amount_cents", new_column_name="prepaid_credit_amount")
    op.alter_column("invoices", "total_cents", new_column_name="total")
    op.alter_column("invoices", "tax_amount_cents", new_column_name="tax_amount")
    op.alter_column("invoices", "subtotal_cents", new_column_name="subtotal")
