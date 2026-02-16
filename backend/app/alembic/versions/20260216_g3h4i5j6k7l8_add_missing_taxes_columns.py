"""add category column to taxes table

Revision ID: g3h4i5j6k7l8
Revises: f2g3h4i5j6k7
Create Date: 2026-02-16

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "g3h4i5j6k7l8"
down_revision = "f2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "taxes",
        sa.Column("category", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("taxes", "category")
