"""create data_exports table

Revision ID: z6u8v9w0x1y2
Revises: y5t7u8v9w0x1
Create Date: 2026-02-12 23:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "z6u8v9w0x1y2"
down_revision = "y5t7u8v9w0x1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_exports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("export_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(length=2048), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_exports_organization_id", "data_exports", ["organization_id"]
    )


def downgrade():
    op.drop_index("ix_data_exports_organization_id", table_name="data_exports")
    op.drop_table("data_exports")
