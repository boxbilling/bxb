"""create features and entitlements tables

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-02-15 18:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "y5z6a7b8c9d0"
down_revision = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "features",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("feature_type", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_features_org_code"
        ),
    )
    op.create_index(
        "ix_features_organization_id",
        "features",
        ["organization_id"],
    )
    op.create_index(
        "ix_features_code",
        "features",
        ["code"],
    )

    op.create_table(
        "entitlements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("feature_id", sa.String(length=36), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["feature_id"],
            ["features.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plan_id", "feature_id", name="uq_entitlements_plan_feature"
        ),
    )
    op.create_index(
        "ix_entitlements_organization_id",
        "entitlements",
        ["organization_id"],
    )
    op.create_index(
        "ix_entitlements_plan_id",
        "entitlements",
        ["plan_id"],
    )
    op.create_index(
        "ix_entitlements_feature_id",
        "entitlements",
        ["feature_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_entitlements_feature_id", table_name="entitlements")
    op.drop_index("ix_entitlements_plan_id", table_name="entitlements")
    op.drop_index("ix_entitlements_organization_id", table_name="entitlements")
    op.drop_table("entitlements")

    op.drop_index("ix_features_code", table_name="features")
    op.drop_index("ix_features_organization_id", table_name="features")
    op.drop_table("features")
