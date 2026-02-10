"""create events table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-10 19:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=False),
        sa.Column("external_customer_id", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id"),
    )
    op.create_index(
        op.f("ix_events_transaction_id"), "events", ["transaction_id"], unique=True
    )
    op.create_index(
        op.f("ix_events_external_customer_id"),
        "events",
        ["external_customer_id"],
        unique=False,
    )
    op.create_index(op.f("ix_events_code"), "events", ["code"], unique=False)
    op.create_index(op.f("ix_events_timestamp"), "events", ["timestamp"], unique=False)
    op.create_index(
        "ix_events_customer_code_timestamp",
        "events",
        ["external_customer_id", "code", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_events_customer_code_timestamp", table_name="events")
    op.drop_index(op.f("ix_events_timestamp"), table_name="events")
    op.drop_index(op.f("ix_events_code"), table_name="events")
    op.drop_index(op.f("ix_events_external_customer_id"), table_name="events")
    op.drop_index(op.f("ix_events_transaction_id"), table_name="events")
    op.drop_table("events")
