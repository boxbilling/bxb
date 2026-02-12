"""create commitments table and add commitment_id to fees

Revision ID: u1p3q4r5s6t7
Revises: t0o2p3q4r5s6
Create Date: 2026-02-12 20:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "u1p3q4r5s6t7"
down_revision = "t0o2p3q4r5s6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create commitments table
    op.create_table(
        "commitments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("commitment_type", sa.String(length=50), nullable=False, server_default="minimum_commitment"),
        sa.Column("amount_cents", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("invoice_display_name", sa.String(length=255), nullable=True),
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
            name="fk_commitments_organization_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            name="fk_commitments_plan_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_commitments_organization_id", "commitments", ["organization_id"])
    op.create_index("ix_commitments_plan_id", "commitments", ["plan_id"])

    # Add commitment_id FK to fees table
    op.add_column("fees", sa.Column("commitment_id", sa.String(length=36), nullable=True))
    op.create_index("ix_fees_commitment_id", "fees", ["commitment_id"])
    op.create_foreign_key(
        "fk_fees_commitment_id",
        "fees",
        "commitments",
        ["commitment_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_fees_commitment_id", "fees", type_="foreignkey")
    op.drop_index("ix_fees_commitment_id", table_name="fees")
    op.drop_column("fees", "commitment_id")
    op.drop_index("ix_commitments_plan_id", table_name="commitments")
    op.drop_index("ix_commitments_organization_id", table_name="commitments")
    op.drop_table("commitments")
