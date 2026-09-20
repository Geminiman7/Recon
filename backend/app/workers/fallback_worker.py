"""Run with python -m app.workers.fallback_worker (independent of Celery)."""
import logging
import signal
import time
from datetime import datetime, timedelta
from threading import Event, Thread
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import OperationalError, InterfaceError
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis_health import circuit
from app.models import company, user, processor, subscription, upload, column_mapping
from app.models.job import ReconciliationJob, JobStatus
from app.models.export_request import ExportRequest
from app.models.resilience import RateBucket, WorkerHeartbeat
from app.services.reconciliation_service import ReconciliationService
from app.services.export_service import generate_export, expire_exports

log = logging.getLogger("recon")


def consume_once(redis_available):
    cutoff = datetime.utcnow() - timedelta(seconds=settings.FALLBACK_GRACE_SECONDS if redis_available else 0)
    worked = False
    with SessionLocal() as db:
        job = db.query(ReconciliationJob).filter(
            ReconciliationJob.status == JobStatus.QUEUED,
            or_(ReconciliationJob.queued_at <= cutoff, ReconciliationJob.queued_at.is_(None)),
        ).order_by(ReconciliationJob.queued_at, ReconciliationJob.id).with_for_update(skip_locked=True).first()
        if job:
            worked = True
            job_id, company_id, token, actor = job.id, job.company_id, job.run_token, job.queued_by
            try:
                ReconciliationService.run(db, company_id, job_id, actor, token)
            except (OperationalError, InterfaceError):
                db.rollback()
                raise
            except Exception:
                db.rollback()
                log.exception("fallback_reconciliation_failed", extra={"job_id": str(job_id)})
                # A database failure leaves the durable row available for a later poll.
                job = db.query(ReconciliationJob).filter(
                    ReconciliationJob.id == job_id, ReconciliationJob.run_token == token,
                    ReconciliationJob.status == JobStatus.QUEUED,
                ).with_for_update().first()
                if job:
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    db.commit()
        else:
            db.rollback()
    with SessionLocal() as db:
        record = db.query(ExportRequest).filter(ExportRequest.state == "PENDING",
            ExportRequest.created_at <= cutoff, ExportRequest.expires_at > datetime.utcnow()
        ).order_by(ExportRequest.created_at, ExportRequest.id).with_for_update(skip_locked=True).first()
        if record:
            worked = True
            generate_export(db, record.id, record.company_id)
    return worked


def healthy(db):
    return db.query(WorkerHeartbeat).filter(
        WorkerHeartbeat.seen_at > datetime.utcnow() - timedelta(seconds=20)
    ).first() is not None


def main():
    logging.basicConfig(level=settings.LOG_LEVEL)
    stop = Event()
    worker_id = str(uuid4())
    progress = [time.monotonic()]
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    def heartbeat():
        while not stop.is_set():
            try:
                # Stop advertising health if execution exceeds the normal task limit.
                if time.monotonic() - progress[0] < 1800:
                    with SessionLocal() as db:
                        db.merge(WorkerHeartbeat(worker_id=worker_id, seen_at=datetime.utcnow()))
                        db.commit()
            except Exception:
                log.exception("fallback_heartbeat_failed")
            stop.wait(5)

    thread = Thread(target=heartbeat, daemon=True)
    thread.start()
    cleanup_at = 0
    try:
        while not stop.is_set():
            progress[0] = time.monotonic()
            try:
                worked = consume_once(circuit.available())
                if time.monotonic() >= cleanup_at:
                    with SessionLocal() as db:
                        db.query(RateBucket).filter(RateBucket.expires_at < datetime.utcnow()).delete()
                        db.query(WorkerHeartbeat).filter(WorkerHeartbeat.seen_at < datetime.utcnow() - timedelta(minutes=5)).delete()
                        db.commit()
                        expire_exports(db)
                    cleanup_at = time.monotonic() + 60
                if not worked:
                    stop.wait(settings.FALLBACK_POLL_SECONDS)
            except Exception:
                log.exception("fallback_poll_failed")
                stop.wait(settings.FALLBACK_POLL_SECONDS)
    finally:
        stop.set()
        thread.join(timeout=6)
        with SessionLocal() as db:
            db.query(WorkerHeartbeat).filter_by(worker_id=worker_id).delete()
            db.commit()


if __name__ == "__main__":
    main()
