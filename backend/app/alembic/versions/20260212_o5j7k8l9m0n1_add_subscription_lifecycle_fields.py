"""add subscription lifecycle fields

Revision ID: o5j7k8l9m0n1
Revises: n4i6j7k8l9m0
Create Date: 2026-02-12 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "o5j7k8l9m0n1"
down_revision = "n4i6j7k8l9m0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("billing_time", sa.String(length=20), nullable=False, server_default="calendar"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("trial_period_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("trial_ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("subscription_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("pay_in_advance", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "subscriptions",
        sa.Column("previous_plan_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("downgraded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "on_termination_action",
            sa.String(length=30),
            nullable=False,
            server_default="generate_invoice",
        ),
    )
    op.create_foreign_key(
        "fk_subscriptions_previous_plan_id",
        "subscriptions",
        "plans",
        ["previous_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_subscriptions_previous_plan_id", "subscriptions", type_="foreignkey")
    op.drop_column("subscriptions", "on_termination_action")
    op.drop_column("subscriptions", "downgraded_at")
    op.drop_column("subscriptions", "previous_plan_id")
    op.drop_column("subscriptions", "pay_in_advance")
    op.drop_column("subscriptions", "subscription_at")
    op.drop_column("subscriptions", "trial_ended_at")
    op.drop_column("subscriptions", "trial_period_days")
    op.drop_column("subscriptions", "billing_time")
