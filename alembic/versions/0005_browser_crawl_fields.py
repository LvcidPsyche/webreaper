"""add browser crawl page fields

Revision ID: 0005_browser_crawl_fields
Revises: 0004_endpoint_inventory
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_browser_crawl_fields"
down_revision = "0004_endpoint_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "pages" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("pages")}
    if "final_url" not in cols:
        op.add_column("pages", sa.Column("final_url", sa.Text()))
    if "fetch_mode" not in cols:
        op.add_column("pages", sa.Column("fetch_mode", sa.String(length=20)))
    if "browser_observed_requests" not in cols:
        op.add_column("pages", sa.Column("browser_observed_requests", sa.JSON()))


def downgrade() -> None:
    pass

