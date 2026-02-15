"""add progress to data_exports

Revision ID: d0e1f2g3h4i5
Revises: c9d0e1f2g3h4
Create Date: 2026-02-15 23:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d0e1f2g3h4i5"
down_revision = "c9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("data_exports", sa.Column("progress", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("data_exports", "progress")
