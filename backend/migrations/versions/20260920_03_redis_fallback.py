"""Durable fallback scheduling and shared rate limits."""
from alembic import op
import sqlalchemy as sa

revision = "20260920_03"
down_revision = "20260907_02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("reconciliation_jobs", sa.Column("queued_at", sa.DateTime()))
    op.add_column("reconciliation_jobs", sa.Column("queued_by", sa.Uuid()))
    op.create_index("ix_jobs_fallback", "reconciliation_jobs", ["status", "queued_at"])
    op.create_index("ix_exports_fallback", "export_requests", ["state", "created_at"])
    op.create_table("rate_buckets", sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=False))
    op.create_index("ix_rate_buckets_expires_at", "rate_buckets", ["expires_at"])
    op.create_table("worker_heartbeats", sa.Column("worker_id", sa.String(36), primary_key=True),
        sa.Column("seen_at", sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table("worker_heartbeats")
    op.drop_table("rate_buckets")
    op.drop_index("ix_exports_fallback", table_name="export_requests")
    op.drop_index("ix_jobs_fallback", table_name="reconciliation_jobs")
    op.drop_column("reconciliation_jobs", "queued_by")
    op.drop_column("reconciliation_jobs", "queued_at")
