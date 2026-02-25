"""add workspaces and workspace linkage columns

Revision ID: 0003_workspace_schema
Revises: 0002_deep_extraction_schema
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_workspace_schema"
down_revision = "0002_deep_extraction_schema"
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "workspaces" not in tables:
        op.create_table(
            "workspaces",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("scope_rules", sa.JSON()),
            sa.Column("tags", sa.JSON()),
            sa.Column("risk_policy", sa.JSON()),
            sa.Column("archived", sa.Boolean(), server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_workspaces_name", "workspaces", ["name"])
        op.create_index("ix_workspaces_archived", "workspaces", ["archived"])
        op.create_index("ix_workspaces_created_at", "workspaces", ["created_at"])

    for table in ("crawls", "pages", "security_findings"):
        cols = _column_names(bind, table)
        if "workspace_id" not in cols:
            op.add_column(table, sa.Column("workspace_id", sa.String(length=36), nullable=True))
            op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])


def downgrade() -> None:
    pass

