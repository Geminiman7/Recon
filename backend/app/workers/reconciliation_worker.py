from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.job import ReconciliationJob, JobStatus
from app.services.activity_service import ActivityService
from app.services.reconciliation_service import ReconciliationService


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_reconciliation_task(self, company_id, job_id, user_id=None, run_token=None):
    db = SessionLocal()
    try:
        ReconciliationService.run(db, UUID(company_id), UUID(job_id), UUID(user_id) if user_id else None, run_token)
    except Exception as exc:
        db.rollback()
        job = db.query(ReconciliationJob).filter(ReconciliationJob.id == UUID(job_id), ReconciliationJob.company_id == UUID(company_id), ReconciliationJob.run_token == run_token).with_for_update().first()
        if not job or job.status == JobStatus.COMPLETED:
            return
        if job:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            db.commit()
        ActivityService.notify_error(
            db,
            UUID(company_id),
            UUID(user_id) if user_id else None,
            "Reconciliation failed",
            "Reconciliation could not complete. Please retry or contact support.",
            "Processing failed",
        )
        ActivityService.audit(
            db,
            UUID(company_id),
            UUID(user_id) if user_id else None,
            "reconciliation.failed",
            "reconciliation_job",
            job_id,
            {"error": "Processing failed"},
        )
        db.commit()
        raise self.retry(exc=exc)
    finally:
        db.close()
