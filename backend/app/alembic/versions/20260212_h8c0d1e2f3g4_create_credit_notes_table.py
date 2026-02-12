"""create credit_notes table

Revision ID: h8c0d1e2f3g4
Revises: g7b9c0d1e2f3
Create Date: 2026-02-12 00:00:07.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "h8c0d1e2f3g4"
down_revision = "g7b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_notes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.String(length=50), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("credit_note_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("credit_status", sa.String(length=20), nullable=True),
        sa.Column("refund_status", sa.String(length=20), nullable=True),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "credit_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "refund_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "balance_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "taxes_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_credit_notes_number", "credit_notes", ["number"])
    op.create_index("ix_credit_notes_invoice_id", "credit_notes", ["invoice_id"])
    op.create_index("ix_credit_notes_customer_id", "credit_notes", ["customer_id"])
    op.create_index("ix_credit_notes_status", "credit_notes", ["status"])


def downgrade() -> None:
    op.drop_index("ix_credit_notes_status", table_name="credit_notes")
    op.drop_index("ix_credit_notes_customer_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_invoice_id", table_name="credit_notes")
    op.drop_index("ix_credit_notes_number", table_name="credit_notes")
    op.drop_table("credit_notes")
