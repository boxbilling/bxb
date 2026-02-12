"""create applied_taxes table

Revision ID: l2g4h5i6j7k8
Revises: k1f3g4h5i6j7
Create Date: 2026-02-12 00:00:11.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "l2g4h5i6j7k8"
down_revision = "k1f3g4h5i6j7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applied_taxes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tax_id", sa.String(length=36), nullable=False),
        sa.Column("taxable_type", sa.String(length=50), nullable=False),
        sa.Column("taxable_id", sa.String(length=36), nullable=False),
        sa.Column("tax_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "tax_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tax_id"], ["taxes.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tax_id", "taxable_type", "taxable_id", name="uq_applied_taxes_unique"),
    )
    op.create_index("ix_applied_taxes_tax_id", "applied_taxes", ["tax_id"])
    op.create_index("ix_applied_taxes_taxable", "applied_taxes", ["taxable_type", "taxable_id"])


def downgrade() -> None:
    op.drop_index("ix_applied_taxes_taxable", table_name="applied_taxes")
    op.drop_index("ix_applied_taxes_tax_id", table_name="applied_taxes")
    op.drop_table("applied_taxes")
