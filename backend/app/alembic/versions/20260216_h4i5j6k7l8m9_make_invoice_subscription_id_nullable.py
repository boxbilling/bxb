"""make invoice subscription_id nullable

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-02-16

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("invoices", "subscription_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    op.alter_column(
        "invoices", "subscription_id", existing_type=sa.String(length=36), nullable=False
    )
