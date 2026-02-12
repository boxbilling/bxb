"""add coupons_amount_cents to invoices

Revision ID: j0e2f3g4h5i6
Revises: i9d1e2f3g4h5
Create Date: 2026-02-12 00:00:09.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "j0e2f3g4h5i6"
down_revision = "i9d1e2f3g4h5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "coupons_amount_cents",
            sa.Numeric(precision=12, scale=4),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "coupons_amount_cents")
