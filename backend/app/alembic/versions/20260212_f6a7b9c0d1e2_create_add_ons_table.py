"""create add_ons table

Revision ID: f6a7b9c0d1e2
Revises: e5f6a7b9c0d1
Create Date: 2026-02-12 00:00:05.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a7b9c0d1e2"
down_revision = "e5f6a7b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "add_ons",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "amount_currency",
            sa.String(length=3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column("invoice_display_name", sa.String(length=255), nullable=True),
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
    op.create_index("ix_add_ons_code", "add_ons", ["code"])


def downgrade() -> None:
    op.drop_index("ix_add_ons_code", table_name="add_ons")
    op.drop_table("add_ons")
