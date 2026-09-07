"""Revocable sessions, fenced jobs, persistent exports and result indexes."""
from alembic import op
import sqlalchemy as sa

revision = "20260907_02"
down_revision = "20260829_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("reconciliation_jobs", sa.Column("run_token", sa.String(36), nullable=True))
    op.create_table("export_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("reconciliation_jobs.id"), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("filter_status", sa.String(40)), sa.Column("search", sa.String(200)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("storage_path", sa.String(500)), sa.Column("error", sa.String(200)),
        sa.Column("row_count", sa.Integer()), sa.Column("run_token", sa.String(36)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False))
    for name in ("company_id", "user_id", "expires_at"):
        op.create_index("ix_export_requests_" + name, "export_requests", [name])
    op.create_index("ix_results_tenant_job_order", "reconciliation_results", ["company_id", "job_id", "transaction_id", "id"])
    op.create_index("ix_results_tenant_job_status", "reconciliation_results", ["company_id", "job_id", "status"])


def downgrade():
    op.drop_index("ix_results_tenant_job_status", table_name="reconciliation_results")
    op.drop_index("ix_results_tenant_job_order", table_name="reconciliation_results")
    op.drop_table("export_requests")
    op.drop_column("reconciliation_jobs", "run_token")
    op.drop_column("users", "session_version")
