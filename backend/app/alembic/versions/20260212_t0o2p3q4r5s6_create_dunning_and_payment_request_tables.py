"""create dunning and payment request tables

Revision ID: t0o2p3q4r5s6
Revises: s9n1o2p3q4r5
Create Date: 2026-02-12 19:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "t0o2p3q4r5s6"
down_revision = "s9n1o2p3q4r5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create dunning_campaigns table
    op.create_table(
        "dunning_campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("days_between_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("bcc_emails", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_dunning_campaigns_organization_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_dunning_campaigns_organization_id",
        "dunning_campaigns",
        ["organization_id"],
    )

    # Create dunning_campaign_thresholds table
    op.create_table(
        "dunning_campaign_thresholds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dunning_campaign_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["dunning_campaign_id"],
            ["dunning_campaigns.id"],
            name="fk_dunning_campaign_thresholds_campaign_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_dunning_campaign_thresholds_campaign_id",
        "dunning_campaign_thresholds",
        ["dunning_campaign_id"],
    )

    # Create payment_requests table
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("dunning_campaign_id", sa.String(length=36), nullable=True),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("amount_currency", sa.String(length=3), nullable=False),
        sa.Column(
            "payment_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payment_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "ready_for_payment_processing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_payment_requests_organization_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_payment_requests_customer_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dunning_campaign_id"],
            ["dunning_campaigns.id"],
            name="fk_payment_requests_dunning_campaign_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_payment_requests_organization_id",
        "payment_requests",
        ["organization_id"],
    )
    op.create_index(
        "ix_payment_requests_customer_id",
        "payment_requests",
        ["customer_id"],
    )
    op.create_index(
        "ix_payment_requests_dunning_campaign_id",
        "payment_requests",
        ["dunning_campaign_id"],
    )

    # Create payment_request_invoices join table
    op.create_table(
        "payment_request_invoices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payment_request_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["payment_request_id"],
            ["payment_requests.id"],
            name="fk_payment_request_invoices_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name="fk_payment_request_invoices_invoice_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_payment_request_invoices_request_id",
        "payment_request_invoices",
        ["payment_request_id"],
    )
    op.create_index(
        "ix_payment_request_invoices_invoice_id",
        "payment_request_invoices",
        ["invoice_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_request_invoices_invoice_id", table_name="payment_request_invoices")
    op.drop_index("ix_payment_request_invoices_request_id", table_name="payment_request_invoices")
    op.drop_table("payment_request_invoices")
    op.drop_index("ix_payment_requests_dunning_campaign_id", table_name="payment_requests")
    op.drop_index("ix_payment_requests_customer_id", table_name="payment_requests")
    op.drop_index("ix_payment_requests_organization_id", table_name="payment_requests")
    op.drop_table("payment_requests")
    op.drop_index("ix_dunning_campaign_thresholds_campaign_id", table_name="dunning_campaign_thresholds")
    op.drop_table("dunning_campaign_thresholds")
    op.drop_index("ix_dunning_campaigns_organization_id", table_name="dunning_campaigns")
    op.drop_table("dunning_campaigns")
