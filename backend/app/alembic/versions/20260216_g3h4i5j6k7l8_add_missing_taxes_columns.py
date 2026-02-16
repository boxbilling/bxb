"""add missing organization_id and category columns to taxes table

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
        sa.Column("organization_id", sa.String(length=36), nullable=False),
    )
    op.add_column(
        "taxes",
        sa.Column("category", sa.String(length=100), nullable=True),
    )
    op.create_foreign_key(
        "fk_taxes_organization_id",
        "taxes",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_taxes_organization_id", "taxes", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_taxes_organization_id", table_name="taxes")
    op.drop_constraint("fk_taxes_organization_id", "taxes", type_="foreignkey")
    op.drop_column("taxes", "category")
    op.drop_column("taxes", "organization_id")
