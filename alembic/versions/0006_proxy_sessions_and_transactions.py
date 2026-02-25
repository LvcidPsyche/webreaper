"""add proxy sessions and http transaction storage

Revision ID: 0006_proxy_sessions_and_transactions
Revises: 0005_browser_crawl_fields
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_proxy_sessions_and_transactions"
down_revision = "0005_browser_crawl_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if "proxy_sessions" not in tables:
        op.create_table(
            "proxy_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True, index=True),
            sa.Column("name", sa.String(length=255)),
            sa.Column("host", sa.String(length=255)),
            sa.Column("port", sa.Integer()),
            sa.Column("intercept_enabled", sa.Boolean()),
            sa.Column("tls_intercept_enabled", sa.Boolean()),
            sa.Column("body_capture_limit_kb", sa.Integer()),
            sa.Column("include_hosts", sa.JSON()),
            sa.Column("exclude_hosts", sa.JSON()),
            sa.Column("status", sa.String(length=20), index=True),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("stopped_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        )

    if "http_transactions" not in tables:
        op.create_table(
            "http_transactions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True, index=True),
            sa.Column("crawl_id", sa.String(length=36), nullable=True, index=True),
            sa.Column("page_id", sa.String(length=36), nullable=True),
            sa.Column("proxy_session_id", sa.String(length=36), nullable=True, index=True),
            sa.Column("source", sa.String(length=20), index=True),
            sa.Column("method", sa.String(length=16), nullable=False, index=True),
            sa.Column("scheme", sa.String(length=10), nullable=False),
            sa.Column("host", sa.String(length=255), nullable=False, index=True),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("query", sa.Text()),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("request_headers", sa.JSON()),
            sa.Column("request_body", sa.Text()),
            sa.Column("response_status", sa.Integer(), index=True),
            sa.Column("response_headers", sa.JSON()),
            sa.Column("response_body", sa.Text()),
            sa.Column("duration_ms", sa.Integer()),
            sa.Column("tags", sa.JSON()),
            sa.Column("intercept_state", sa.String(length=20), index=True),
            sa.Column("truncated", sa.Boolean()),
            sa.Column("created_at", sa.DateTime(timezone=True), index=True),
        )


def downgrade() -> None:
    pass

