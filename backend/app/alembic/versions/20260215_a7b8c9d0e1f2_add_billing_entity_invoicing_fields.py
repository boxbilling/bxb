"""add invoice_grace_period, net_payment_term, invoice_footer to billing_entities

Revision ID: a7b8c9d0e1f2
Revises: z6a7b8c9d0e1
Create Date: 2026-02-15 22:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_entities",
        sa.Column(
            "invoice_grace_period",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "billing_entities",
        sa.Column(
            "net_payment_term",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "billing_entities",
        sa.Column("invoice_footer", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billing_entities", "invoice_footer")
    op.drop_column("billing_entities", "net_payment_term")
    op.drop_column("billing_entities", "invoice_grace_period")
