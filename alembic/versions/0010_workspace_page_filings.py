"""add workspace page filing table

Revision ID: 0010_workspace_page_filings
Revises: 0009_governance_triage_profiles_automation
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_workspace_page_filings"
down_revision = "0009_governance_triage_profiles_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if "workspace_page_filings" in tables:
        return

    op.create_table(
        "workspace_page_filings",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("page_id", sa.String(length=36), nullable=False),
        sa.Column("folder", sa.String(length=255)),
        sa.Column("category", sa.String(length=50)),
        sa.Column("labels", sa.JSON()),
        sa.Column("notes", sa.Text()),
        sa.Column("starred", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workspace_id", "page_id", name="uq_workspace_page_filing"),
    )
    op.create_index("ix_workspace_page_filings_workspace_id", "workspace_page_filings", ["workspace_id"])
    op.create_index("ix_workspace_page_filings_page_id", "workspace_page_filings", ["page_id"])
    op.create_index("ix_workspace_page_filings_folder", "workspace_page_filings", ["folder"])
    op.create_index("ix_workspace_page_filings_category", "workspace_page_filings", ["category"])
    op.create_index("ix_workspace_page_filings_starred", "workspace_page_filings", ["starred"])


def downgrade() -> None:
    pass
