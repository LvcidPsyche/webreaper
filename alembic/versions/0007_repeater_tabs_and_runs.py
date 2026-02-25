"""add repeater tabs and runs

Revision ID: 0007_repeater_tabs_and_runs
Revises: 0006_proxy_sessions_and_transactions
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_repeater_tabs_and_runs"
down_revision = "0006_proxy_sessions_and_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if "repeater_tabs" not in tables:
        op.create_table(
            "repeater_tabs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True),
            sa.Column("source_transaction_id", sa.String(length=36), nullable=True),
            sa.Column("name", sa.String(length=255)),
            sa.Column("method", sa.String(length=16), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("headers", sa.JSON()),
            sa.Column("body", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.Column("last_run_at", sa.DateTime(timezone=True)),
        )

    if "repeater_runs" not in tables:
        op.create_table(
            "repeater_runs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("repeater_tab_id", sa.String(length=36), nullable=False),
            sa.Column("workspace_id", sa.String(length=36), nullable=True),
            sa.Column("transaction_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("response_status", sa.Integer()),
            sa.Column("duration_ms", sa.Integer()),
            sa.Column("timeout_ms", sa.Integer()),
            sa.Column("follow_redirects", sa.Boolean()),
            sa.Column("error", sa.Text()),
            sa.Column("diff_summary", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True)),
        )


def downgrade() -> None:
    pass
