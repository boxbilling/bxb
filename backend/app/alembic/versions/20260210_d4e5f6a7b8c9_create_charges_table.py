"""create charges table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-10 19:10:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "charges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("billable_metric_id", sa.String(length=36), nullable=False),
        sa.Column("charge_model", sa.String(length=20), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False, server_default="{}"),
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
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["billable_metric_id"], ["billable_metrics.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_charges_plan_id"), "charges", ["plan_id"], unique=False)
    op.create_index(op.f("ix_charges_billable_metric_id"), "charges", ["billable_metric_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_charges_billable_metric_id"), table_name="charges")
    op.drop_index(op.f("ix_charges_plan_id"), table_name="charges")
    op.drop_table("charges")
