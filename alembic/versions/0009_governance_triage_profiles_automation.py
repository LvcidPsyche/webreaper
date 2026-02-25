"""add governance, triage, profiles, and automation tables

Revision ID: 0009_governance_triage_profiles_automation
Revises: 0008_intruder_jobs_and_results
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = '0009_governance_triage_profiles_automation'
down_revision = '0008_intruder_jobs_and_results'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if 'finding_triage' not in tables:
        op.create_table(
            'finding_triage',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('finding_id', sa.String(length=36), nullable=False, unique=True),
            sa.Column('workspace_id', sa.String(length=36), nullable=True),
            sa.Column('status', sa.String(length=20)),
            sa.Column('assignee', sa.String(length=255)),
            sa.Column('tags', sa.JSON()),
            sa.Column('notes', sa.Text()),
            sa.Column('endpoint_id', sa.String(length=36), nullable=True),
            sa.Column('transaction_id', sa.String(length=36), nullable=True),
            sa.Column('reproduction_steps', sa.JSON()),
            sa.Column('evidence_refs', sa.JSON()),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
            sa.Column('triaged_at', sa.DateTime(timezone=True)),
        )

    if 'audit_logs' not in tables:
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('workspace_id', sa.String(length=36), nullable=True),
            sa.Column('actor', sa.String(length=255)),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('resource_type', sa.String(length=50)),
            sa.Column('resource_id', sa.String(length=36)),
            sa.Column('allowed', sa.Boolean()),
            sa.Column('policy_rule', sa.String(length=100)),
            sa.Column('reason', sa.Text()),
            sa.Column('details', sa.JSON()),
            sa.Column('created_at', sa.DateTime(timezone=True)),
        )

    if 'run_profiles' not in tables:
        op.create_table(
            'run_profiles',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('workspace_id', sa.String(length=36), nullable=True),
            sa.Column('profile_type', sa.String(length=20), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('settings', sa.JSON()),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'ui_preferences' not in tables:
        op.create_table(
            'ui_preferences',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('workspace_id', sa.String(length=36), nullable=True),
            sa.Column('user_id', sa.String(length=255)),
            sa.Column('page', sa.String(length=50), nullable=False),
            sa.Column('key', sa.String(length=100), nullable=False),
            sa.Column('value', sa.JSON()),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'automation_runs' not in tables:
        op.create_table(
            'automation_runs',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('workspace_id', sa.String(length=36), nullable=True),
            sa.Column('profile_id', sa.String(length=36), nullable=True),
            sa.Column('name', sa.String(length=255)),
            sa.Column('chain', sa.JSON()),
            sa.Column('inputs', sa.JSON()),
            sa.Column('outputs', sa.JSON()),
            sa.Column('status', sa.String(length=20)),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('completed_at', sa.DateTime(timezone=True)),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )


def downgrade() -> None:
    pass
