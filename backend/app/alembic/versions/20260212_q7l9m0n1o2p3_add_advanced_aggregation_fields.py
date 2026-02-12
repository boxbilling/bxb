"""add advanced aggregation fields to billable_metrics

Revision ID: q7l9m0n1o2p3
Revises: p6k8l9m0n1o2
Create Date: 2026-02-12 15:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "q7l9m0n1o2p3"
down_revision = "p6k8l9m0n1o2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billable_metrics",
        sa.Column("recurring", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "billable_metrics",
        sa.Column("rounding_function", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "billable_metrics",
        sa.Column("rounding_precision", sa.Integer(), nullable=True),
    )
    op.add_column(
        "billable_metrics",
        sa.Column("expression", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billable_metrics", "expression")
    op.drop_column("billable_metrics", "rounding_precision")
    op.drop_column("billable_metrics", "rounding_function")
    op.drop_column("billable_metrics", "recurring")
