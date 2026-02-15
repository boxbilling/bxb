"""add paused_at and resumed_at to subscriptions

Revision ID: 3c64bd9b45ce
Revises: d0e1f2g3h4i5
Create Date: 2026-02-15
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3c64bd9b45ce"
down_revision = "d0e1f2g3h4i5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "resumed_at")
    op.drop_column("subscriptions", "paused_at")
