"""create organizations table and add organization_id to all existing tables

Revision ID: r8m0n1o2p3q4
Revises: q7l9m0n1o2p3
Create Date: 2026-02-12 17:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "r8m0n1o2p3q4"
down_revision = "q7l9m0n1o2p3"
branch_labels = None
depends_on = None

# Known default organization ID for backfilling existing data
DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# Tables that need organization_id added
TABLES_TO_SCOPE = [
    "customers",
    "plans",
    "billable_metrics",
    "charges",
    "subscriptions",
    "events",
    "invoices",
    "payments",
    "fees",
    "wallets",
    "wallet_transactions",
    "coupons",
    "applied_coupons",
    "add_ons",
    "credit_notes",
    "taxes",
    "webhook_endpoints",
]

# Tables that have a unique 'code' column needing composite unique with organization_id
CODE_UNIQUE_TABLES = [
    "plans",
    "billable_metrics",
    "coupons",
    "add_ons",
    "taxes",
]

# Tables that have a unique 'external_id' column
EXTERNAL_ID_UNIQUE_TABLES = [
    "customers",
]


def upgrade() -> None:
    # 1. Create the organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("hmac_key", sa.String(length=255), nullable=True),
        sa.Column("document_number_prefix", sa.String(length=20), nullable=True),
        sa.Column("invoice_grace_period", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_payment_term", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("logo_url", sa.String(length=2048), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("zipcode", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Insert default organization for existing data
    organizations_table = sa.table(
        "organizations",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("default_currency", sa.String),
        sa.column("timezone", sa.String),
    )
    op.bulk_insert(
        organizations_table,
        [
            {
                "id": DEFAULT_ORG_ID,
                "name": "Default Organization",
                "default_currency": "USD",
                "timezone": "UTC",
            }
        ],
    )

    # 3. Add organization_id column to all existing tables (nullable initially)
    for table_name in TABLES_TO_SCOPE:
        op.add_column(
            table_name,
            sa.Column(
                "organization_id",
                sa.String(length=36),
                nullable=True,
            ),
        )

    # 4. Backfill organization_id with default org for all existing rows
    for table_name in TABLES_TO_SCOPE:
        table = sa.table(
            table_name,
            sa.column("organization_id", sa.String),
        )
        op.execute(table.update().values(organization_id=DEFAULT_ORG_ID))

    # 5. Make organization_id NOT NULL after backfill
    #    SQLite requires batch mode for column alterations
    for table_name in TABLES_TO_SCOPE:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("organization_id", nullable=False)
            batch_op.create_foreign_key(
                f"fk_{table_name}_organization_id",
                "organizations",
                ["organization_id"],
                ["id"],
            )

    # 6. Create indexes on organization_id for all scoped tables
    for table_name in TABLES_TO_SCOPE:
        op.create_index(
            f"ix_{table_name}_organization_id",
            table_name,
            ["organization_id"],
        )

    # 7. Add composite unique indexes for code-based tables
    for table_name in CODE_UNIQUE_TABLES:
        op.create_index(
            f"ix_{table_name}_org_code",
            table_name,
            ["organization_id", "code"],
            unique=True,
        )

    # 8. Add composite unique index for external_id-based tables
    for table_name in EXTERNAL_ID_UNIQUE_TABLES:
        op.create_index(
            f"ix_{table_name}_org_external_id",
            table_name,
            ["organization_id", "external_id"],
            unique=True,
        )


def downgrade() -> None:
    # Remove composite unique indexes
    for table_name in EXTERNAL_ID_UNIQUE_TABLES:
        op.drop_index(f"ix_{table_name}_org_external_id", table_name=table_name)

    for table_name in CODE_UNIQUE_TABLES:
        op.drop_index(f"ix_{table_name}_org_code", table_name=table_name)

    # Remove organization_id indexes and columns
    for table_name in TABLES_TO_SCOPE:
        op.drop_index(f"ix_{table_name}_organization_id", table_name=table_name)

    for table_name in TABLES_TO_SCOPE:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(f"fk_{table_name}_organization_id", type_="foreignkey")
            batch_op.drop_column("organization_id")

    op.drop_table("organizations")
