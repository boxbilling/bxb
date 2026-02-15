"""Add portal branding fields to organizations.

Revision ID: e1f2g3h4i5j6
Revises: c9d0e1f2g3h4
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa

revision = "e1f2g3h4i5j6"
down_revision = "3c64bd9b45ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("portal_accent_color", sa.String(7), nullable=True))
    op.add_column("organizations", sa.Column("portal_welcome_message", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "portal_welcome_message")
    op.drop_column("organizations", "portal_accent_color")
