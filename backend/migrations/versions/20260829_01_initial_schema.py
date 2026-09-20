"""Create the Recon application schema.

Revision ID: 20260829_01
Revises:
Create Date: 2026-08-29 00:00:00
"""

from alembic import op
from sqlalchemy import MetaData
from app.core.database import Base
from app.models import audit_log, column_mapping, company, job, notification
from app.models import password_reset_token, processor, reconciliation_result, subscription, upload, user

def initial_metadata():
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in {"export_requests", "rate_buckets", "worker_heartbeats"}:
            table.to_metadata(metadata)
    jobs = metadata.tables["reconciliation_jobs"]
    for index in list(jobs.indexes):
        if index.name == "ix_jobs_fallback":
            jobs.indexes.remove(index)
    for table_name, column in [("users", "session_version"), ("reconciliation_jobs", "run_token"), ("reconciliation_jobs", "queued_at"), ("reconciliation_jobs", "queued_by")]:
        table = metadata.tables[table_name]
        if column in table.c:
            table._columns.remove(table.c[column])
    table = metadata.tables["reconciliation_results"]
    for index in list(table.indexes):
        if index.name in {"ix_results_tenant_job_order", "ix_results_tenant_job_status"}:
            table.indexes.remove(index)
    return metadata


revision = "20260829_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the schema represented by the initial application models."""
    initial_metadata().create_all(bind=op.get_bind())


def downgrade() -> None:
    """Remove all application tables, including their PostgreSQL enum types."""
    initial_metadata().drop_all(bind=op.get_bind())
