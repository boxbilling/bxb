"""create integration tables

Revision ID: x4s6t7u8v9w0
Revises: w3r5s6t7u8v9
Create Date: 2026-02-12 23:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "x4s6t7u8v9w0"
down_revision = "w3r5s6t7u8v9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # integrations table
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("integration_type", sa.String(length=30), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider_type", name="uq_integrations_org_provider"),
    )
    op.create_index("ix_integrations_organization_id", "integrations", ["organization_id"], unique=False)

    # integration_mappings table
    op.create_table(
        "integration_mappings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("integration_id", sa.String(length=36), nullable=False),
        sa.Column("mappable_type", sa.String(length=50), nullable=False),
        sa.Column("mappable_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_data", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id", "mappable_type", "mappable_id",
            name="uq_integration_mappings_integration_type_id",
        ),
    )
    op.create_index("ix_integration_mappings_integration_id", "integration_mappings", ["integration_id"], unique=False)

    # integration_customers table
    op.create_table(
        "integration_customers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("integration_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("external_customer_id", sa.String(length=255), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id", "customer_id",
            name="uq_integration_customers_integration_customer",
        ),
    )
    op.create_index("ix_integration_customers_integration_id", "integration_customers", ["integration_id"], unique=False)
    op.create_index("ix_integration_customers_customer_id", "integration_customers", ["customer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_integration_customers_customer_id", table_name="integration_customers")
    op.drop_index("ix_integration_customers_integration_id", table_name="integration_customers")
    op.drop_table("integration_customers")
    op.drop_index("ix_integration_mappings_integration_id", table_name="integration_mappings")
    op.drop_table("integration_mappings")
    op.drop_index("ix_integrations_organization_id", table_name="integrations")
    op.drop_table("integrations")
