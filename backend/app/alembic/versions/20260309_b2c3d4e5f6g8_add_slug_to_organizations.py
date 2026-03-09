"""add slug to organizations

Revision ID: b2c3d4e5f6g8
Revises: a1b2c3d4e5g7
Create Date: 2026-03-09

"""

import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g8"
down_revision = "a1b2c3d4e5g7"
branch_labels = None
depends_on = None


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-") or "org"


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("slug", sa.String(255), nullable=True),
    )

    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id, name FROM organizations")).fetchall()
    seen_slugs: dict[str, int] = {}
    for org_id, name in orgs:
        base_slug = _slugify(name)
        slug = base_slug
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{base_slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 0
        conn.execute(
            sa.text("UPDATE organizations SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": org_id},
        )

    op.alter_column("organizations", "slug", nullable=False)
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_column("organizations", "slug")
