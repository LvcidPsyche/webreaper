"""baseline schema (current ORM create_all bootstrap)

Revision ID: 0001_baseline_schema
Revises:
Create Date: 2026-02-25
"""

from alembic import op

from webreaper.database import Base

# revision identifiers, used by Alembic.
revision = "0001_baseline_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all ORM-declared tables for fresh installs.

    Existing installs may already have a subset of tables/columns; create_all is
    additive for missing tables only. Follow-up migrations handle missing
    columns/tables introduced after legacy installs.
    """
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
