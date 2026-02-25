"""add endpoint inventory table

Revision ID: 0004_endpoint_inventory
Revises: 0003_workspace_schema
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_endpoint_inventory"
down_revision = "0003_workspace_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "endpoints" in inspector.get_table_names():
        return

    op.create_table(
        "endpoints",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("crawl_id", sa.String(length=36), sa.ForeignKey("crawls.id", ondelete="CASCADE"), index=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=True, index=True),
        sa.Column("page_id", sa.String(length=36), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("host", sa.String(length=255), index=True),
        sa.Column("scheme", sa.String(length=10), index=True),
        sa.Column("method", sa.String(length=16), index=True),
        sa.Column("path", sa.Text(), index=True),
        sa.Column("query_params", sa.JSON()),
        sa.Column("body_param_names", sa.JSON()),
        sa.Column("content_types", sa.JSON()),
        sa.Column("sources", sa.JSON()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    pass

