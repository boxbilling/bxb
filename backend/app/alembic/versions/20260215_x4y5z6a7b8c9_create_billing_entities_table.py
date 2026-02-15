"""create billing_entities table and add billing_entity_id to related models

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-02-15 16:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("zip_code", sa.String(length=20), nullable=True),
        sa.Column("tax_id", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column(
            "timezone",
            sa.String(length=50),
            nullable=False,
            server_default="UTC",
        ),
        sa.Column(
            "document_locale",
            sa.String(length=10),
            nullable=False,
            server_default="en",
        ),
        sa.Column("invoice_prefix", sa.String(length=20), nullable=True),
        sa.Column(
            "next_invoice_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_billing_entities_organization_id",
        "billing_entities",
        ["organization_id"],
    )
    op.create_index(
        "ix_billing_entities_code",
        "billing_entities",
        ["code"],
    )

    # Add billing_entity_id FK to invoices
    op.add_column(
        "invoices",
        sa.Column("billing_entity_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_invoices_billing_entity_id",
        "invoices",
        ["billing_entity_id"],
    )
    op.create_foreign_key(
        "fk_invoices_billing_entity_id",
        "invoices",
        "billing_entities",
        ["billing_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add billing_entity_id FK to subscriptions
    op.add_column(
        "subscriptions",
        sa.Column("billing_entity_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_subscriptions_billing_entity_id",
        "subscriptions",
        ["billing_entity_id"],
    )
    op.create_foreign_key(
        "fk_subscriptions_billing_entity_id",
        "subscriptions",
        "billing_entities",
        ["billing_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add billing_entity_id FK to customers
    op.add_column(
        "customers",
        sa.Column("billing_entity_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_customers_billing_entity_id",
        "customers",
        ["billing_entity_id"],
    )
    op.create_foreign_key(
        "fk_customers_billing_entity_id",
        "customers",
        "billing_entities",
        ["billing_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Remove billing_entity_id from customers
    op.drop_constraint(
        "fk_customers_billing_entity_id", "customers", type_="foreignkey"
    )
    op.drop_index("ix_customers_billing_entity_id", table_name="customers")
    op.drop_column("customers", "billing_entity_id")

    # Remove billing_entity_id from subscriptions
    op.drop_constraint(
        "fk_subscriptions_billing_entity_id",
        "subscriptions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_subscriptions_billing_entity_id", table_name="subscriptions"
    )
    op.drop_column("subscriptions", "billing_entity_id")

    # Remove billing_entity_id from invoices
    op.drop_constraint(
        "fk_invoices_billing_entity_id", "invoices", type_="foreignkey"
    )
    op.drop_index("ix_invoices_billing_entity_id", table_name="invoices")
    op.drop_column("invoices", "billing_entity_id")

    # Drop billing_entities table
    op.drop_index("ix_billing_entities_code", table_name="billing_entities")
    op.drop_index(
        "ix_billing_entities_organization_id", table_name="billing_entities"
    )
    op.drop_table("billing_entities")
