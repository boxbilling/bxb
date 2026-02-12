"""create taxes table

Revision ID: k1f3g4h5i6j7
Revises: j0e2f3g4h5i6
Create Date: 2026-02-12 00:00:10.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "k1f3g4h5i6j7"
down_revision = "j0e2f3g4h5i6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("applied_to_organization", sa.Boolean(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_taxes_code", "taxes", ["code"])


def downgrade() -> None:
    op.drop_index("ix_taxes_code", table_name="taxes")
    op.drop_table("taxes")
