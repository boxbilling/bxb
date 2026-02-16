"""Drop invoicing columns from organizations table.

Revision ID: f2g3h4i5j6k7
Revises: 01c86d212a9e
Create Date: 2026-02-16
"""

from alembic import op

revision = "f2g3h4i5j6k7"
down_revision = "01c86d212a9e"
branch_labels = None
depends_on = None

COLUMNS_TO_DROP = [
    "document_number_prefix",
    "invoice_grace_period",
    "net_payment_term",
    "email",
    "legal_name",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "zipcode",
    "country",
]


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        for col in COLUMNS_TO_DROP:
            batch_op.drop_column(col)


def downgrade() -> None:
    import sqlalchemy as sa

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(sa.Column("country", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("zipcode", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("state", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("address_line2", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_line1", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("legal_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "net_payment_term",
                sa.Integer(),
                nullable=False,
                server_default="30",
            )
        )
        batch_op.add_column(
            sa.Column(
                "invoice_grace_period",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "document_number_prefix", sa.String(length=20), nullable=True
            )
        )
