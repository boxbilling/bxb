"""create idempotency_records table

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-02-15 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_method", sa.String(length=10), nullable=False),
        sa.Column("request_path", sa.String(length=500), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
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
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_org_idempotency_key"
        ),
    )
    op.create_index(
        "ix_idempotency_records_organization_id",
        "idempotency_records",
        ["organization_id"],
    )
    op.create_index(
        "ix_idempotency_records_idempotency_key",
        "idempotency_records",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_idempotency_records_idempotency_key", table_name="idempotency_records"
    )
    op.drop_index(
        "ix_idempotency_records_organization_id", table_name="idempotency_records"
    )
    op.drop_table("idempotency_records")
