"""create credit_note_items table

Revision ID: i9d1e2f3g4h5
Revises: h8c0d1e2f3g4
Create Date: 2026-02-12 00:00:08.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "i9d1e2f3g4h5"
down_revision = "h8c0d1e2f3g4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_note_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("credit_note_id", sa.String(length=36), nullable=False),
        sa.Column("fee_id", sa.String(length=36), nullable=False),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.ForeignKeyConstraint(
            ["credit_note_id"], ["credit_notes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["fee_id"], ["fees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_credit_note_items_credit_note_id",
        "credit_note_items",
        ["credit_note_id"],
    )
    op.create_index("ix_credit_note_items_fee_id", "credit_note_items", ["fee_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_note_items_fee_id", table_name="credit_note_items")
    op.drop_index(
        "ix_credit_note_items_credit_note_id", table_name="credit_note_items"
    )
    op.drop_table("credit_note_items")
