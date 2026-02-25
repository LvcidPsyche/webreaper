"""add deep extraction page fields and inventory tables

Revision ID: 0002_deep_extraction_schema
Revises: 0001_baseline_schema
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_deep_extraction_schema"
down_revision = "0001_baseline_schema"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    # Legacy installs may not have these inventory tables. Fresh installs created
    # from 0001 (current ORM metadata) already include them, so we guard on name.
    if "assets" not in tables:
        op.create_table(
            "assets",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("page_id", sa.String(length=36), sa.ForeignKey("pages.id", ondelete="CASCADE")),
            sa.Column("crawl_id", sa.String(length=36), sa.ForeignKey("crawls.id", ondelete="CASCADE"), index=True),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("asset_type", sa.String(length=20), nullable=False, index=True),
            sa.Column("alt_text", sa.Text()),
            sa.Column("is_external", sa.Boolean(), default=False, index=True),
            sa.Column("loading", sa.String(length=10)),
            sa.Column("attributes", sa.JSON()),
            sa.Column("discovered_at", sa.DateTime(timezone=True)),
        )

    if "technologies" not in tables:
        op.create_table(
            "technologies",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("crawl_id", sa.String(length=36), sa.ForeignKey("crawls.id", ondelete="CASCADE"), index=True),
            sa.Column("page_id", sa.String(length=36), sa.ForeignKey("pages.id", ondelete="CASCADE")),
            sa.Column("domain", sa.String(length=255), index=True),
            sa.Column("category", sa.String(length=30), nullable=False, index=True),
            sa.Column("name", sa.String(length=100), nullable=False, index=True),
            sa.Column("confidence", sa.Float(), default=0.8),
            sa.Column("detected_at", sa.DateTime(timezone=True)),
        )

    if "pages" not in tables:
        # Fresh DBs should already have pages via baseline. If not, bail and let
        # baseline be applied first.
        return

    page_cols = _column_names(bind, "pages")
    additions = [
        ("meta_tags", sa.JSON()),
        ("og_data", sa.JSON()),
        ("twitter_card", sa.JSON()),
        ("structured_data", sa.JSON()),
        ("technologies", sa.JSON()),
        ("emails_found", sa.JSON()),
        ("phone_numbers", sa.JSON()),
        ("addresses_found", sa.JSON()),
        ("social_links", sa.JSON()),
        ("seo_score", sa.Integer()),
        ("seo_issues", sa.JSON()),
        ("seo_passes", sa.JSON()),
        ("readability_score", sa.Float()),
        ("reading_level", sa.String(length=30)),
        ("content_to_html_ratio", sa.Float()),
        ("sentence_count", sa.Integer()),
        ("unique_word_count", sa.Integer()),
        ("top_words", sa.JSON()),
        ("content_hash", sa.String(length=16)),
        ("language", sa.String(length=10)),
        ("favicon_url", sa.Text()),
        ("robots_meta", sa.Text()),
        ("hreflang", sa.JSON()),
        ("has_canonical", sa.Boolean()),
        ("scripts_count", sa.Integer()),
        ("stylesheets_count", sa.Integer()),
        ("forms_count", sa.Integer()),
        ("total_resource_count", sa.Integer()),
    ]
    for name, coltype in additions:
        if name not in page_cols:
            op.add_column("pages", sa.Column(name, coltype))


def downgrade() -> None:
    # Intentionally conservative: destructive schema downgrades are risky for
    # user data. Use backups/restores for rollback.
    pass
