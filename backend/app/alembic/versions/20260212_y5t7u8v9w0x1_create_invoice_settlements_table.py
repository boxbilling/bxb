"""create invoice_settlements table

Revision ID: y5t7u8v9w0x1
Revises: x4s6t7u8v9w0
Create Date: 2026-02-12 23:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "y5t7u8v9w0x1"
down_revision = "x4s6t7u8v9w0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice_settlements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("settlement_type", sa.String(length=20), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_settlements_invoice_id", "invoice_settlements", ["invoice_id"])
    op.create_index(
        "ix_invoice_settlements_type_source",
        "invoice_settlements",
        ["settlement_type", "source_id"],
    )


def downgrade():
    op.drop_index("ix_invoice_settlements_type_source", table_name="invoice_settlements")
    op.drop_index("ix_invoice_settlements_invoice_id", table_name="invoice_settlements")
    op.drop_table("invoice_settlements")
