"""add intruder jobs and results

Revision ID: 0008_intruder_jobs_and_results
Revises: 0007_repeater_tabs_and_runs
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = '0008_intruder_jobs_and_results'
down_revision = '0007_repeater_tabs_and_runs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if 'intruder_jobs' not in tables:
        op.create_table(
            'intruder_jobs',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('workspace_id', sa.String(length=36), nullable=True),
            sa.Column('source_transaction_id', sa.String(length=36), nullable=True),
            sa.Column('name', sa.String(length=255)),
            sa.Column('method', sa.String(length=16), nullable=False),
            sa.Column('url', sa.Text(), nullable=False),
            sa.Column('headers', sa.JSON()),
            sa.Column('body', sa.Text()),
            sa.Column('payloads', sa.JSON()),
            sa.Column('payload_markers', sa.JSON()),
            sa.Column('attack_type', sa.String(length=20)),
            sa.Column('concurrency', sa.Integer()),
            sa.Column('rate_limit_rps', sa.Float()),
            sa.Column('timeout_ms', sa.Integer()),
            sa.Column('follow_redirects', sa.Boolean()),
            sa.Column('match_substring', sa.Text()),
            sa.Column('stop_on_statuses', sa.JSON()),
            sa.Column('stop_on_first_match', sa.Boolean()),
            sa.Column('status', sa.String(length=20)),
            sa.Column('total_attempts', sa.Integer()),
            sa.Column('completed_attempts', sa.Integer()),
            sa.Column('matched_attempts', sa.Integer()),
            sa.Column('cancelled', sa.Boolean()),
            sa.Column('last_error', sa.Text()),
            sa.Column('started_at', sa.DateTime(timezone=True)),
            sa.Column('completed_at', sa.DateTime(timezone=True)),
            sa.Column('created_at', sa.DateTime(timezone=True)),
            sa.Column('updated_at', sa.DateTime(timezone=True)),
        )

    if 'intruder_results' not in tables:
        op.create_table(
            'intruder_results',
            sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
            sa.Column('job_id', sa.String(length=36), nullable=False),
            sa.Column('attempt_index', sa.Integer(), nullable=False),
            sa.Column('payload', sa.Text()),
            sa.Column('request_url', sa.Text()),
            sa.Column('request_body', sa.Text()),
            sa.Column('transaction_id', sa.String(length=36), nullable=True),
            sa.Column('response_status', sa.Integer()),
            sa.Column('duration_ms', sa.Integer()),
            sa.Column('matched', sa.Boolean()),
            sa.Column('match_reason', sa.Text()),
            sa.Column('error', sa.Text()),
            sa.Column('created_at', sa.DateTime(timezone=True)),
        )


def downgrade() -> None:
    pass
