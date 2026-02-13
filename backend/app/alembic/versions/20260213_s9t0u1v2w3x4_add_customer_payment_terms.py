"""add invoice_grace_period and net_payment_term to customers

Revision ID: s9t0u1v2w3x4
Revises: r8m0n1o2p3q4
Create Date: 2026-02-13 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "s9t0u1v2w3x4"
down_revision = "a7v9w0x1y2z3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("invoice_grace_period", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "customers",
        sa.Column("net_payment_term", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    with op.batch_alter_table("customers") as batch_op:
        batch_op.drop_column("net_payment_term")
        batch_op.drop_column("invoice_grace_period")
