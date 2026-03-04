"""drop items table

Revision ID: a1b2c3d4e5g7
Revises: h4i5j6k7l8m9
Create Date: 2026-03-04

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5g7"
down_revision = "h4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f("ix_items_id"), table_name="items")
    op.drop_table("items")


def downgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_items_id"), "items", ["id"], unique=False)
