"""Bounded background exports with private, expiring storage."""
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import logging
from fastapi import HTTPException
from app.core.config import settings
from app.models.export_request import ExportRequest
from app.models.job import ReconciliationJob, JobStatus
from app.models.user import User
from app.models.reconciliation_result import ReconciliationResult
from app.services.result_service import owned_job, result_query, serialize_result
from app.services.export_writers import write_excel, write_pdf, MIME, EXTENSION
from app.services import storage_service as storage


def bounded_rows(query):
    for number, row in enumerate(query.order_by(ReconciliationResult.transaction_id, ReconciliationResult.id).yield_per(500), 1):
        if number > settings.EXPORT_MAX_ROWS:
            raise ValueError("Too many export rows. Narrow the filters.")
        yield serialize_result(row)


def create_export(db, current_user, job_id, format, status=None, search=None):
    job = owned_job(db, current_user.company_id, job_id)
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(409, "Finish reconciliation before exporting.")
    if result_query(db, current_user.company_id, job_id, status, search).count() > settings.EXPORT_MAX_ROWS:
        raise HTTPException(422, "Too many export rows. Narrow the filters.")
    db.query(User).filter(User.id == current_user.id).with_for_update().one()
    active = db.query(ExportRequest).filter(ExportRequest.user_id == current_user.id,
        ExportRequest.state.in_(["PENDING", "PROCESSING"]), ExportRequest.expires_at > datetime.utcnow()).count()
    if active >= 2:
        raise HTTPException(429, "Wait for your current exports to finish.")
    record = ExportRequest(company_id=current_user.company_id, user_id=current_user.id, job_id=job_id,
        format=format, filter_status=status, search=search, run_token=job.run_token,
        expires_at=datetime.utcnow() + timedelta(hours=settings.EXPORT_TTL_HOURS))
    db.add(record)
    db.commit()
    from app.workers.export_worker import build_export
    try:
        build_export.delay(str(record.id), str(current_user.company_id))
    except Exception:
        logging.getLogger("recon").exception("Export queue publish failed")
        record.state = "FAILED"
        record.error = "Export queue is unavailable. Please try again."
        db.commit()
        raise HTTPException(503, record.error)
    return record


def generate_export(db, export_id, company_id):
    # Duplicate deliveries serialize; a process crash releases these row locks.
    record = db.query(ExportRequest).filter(ExportRequest.id == export_id,
        ExportRequest.company_id == company_id).with_for_update().first()
    if not record or record.state in {"READY", "FAILED"} or record.expires_at <= datetime.utcnow():
        return
    job = db.query(ReconciliationJob).filter(ReconciliationJob.id == record.job_id,
        ReconciliationJob.company_id == company_id).with_for_update(read=True).first()
    if not job or job.status != JobStatus.COMPLETED or job.run_token != record.run_token:
        record.state = "FAILED"
        record.error = "Results changed. Request a new export."
        db.commit()
        return
    record.state = "PROCESSING"
    reference = None
    try:
        with TemporaryDirectory(prefix="recon-export-") as folder:
            path = Path(folder) / f"{record.id}.{EXTENSION[record.format]}"
            rows = bounded_rows(result_query(db, company_id, record.job_id, record.filter_status, record.search))
            record.row_count = (write_excel if record.format == "excel" else write_pdf)(rows, path)
            if path.stat().st_size > settings.EXPORT_MAX_BYTES:
                raise ValueError("Export exceeds the size limit. Narrow the filters.")
            reference = storage.put_file(path, f"exports/{company_id}/{record.id}.{EXTENSION[record.format]}", MIME[record.format])
        record.storage_path = reference
        record.state = "READY"
        db.commit()
    except Exception:
        logging.getLogger("recon").exception("Export generation failed", extra={"export_id": str(export_id)})
        db.rollback()
        if reference:
            try:
                storage.delete_file(reference)
            except Exception:
                logging.getLogger("recon").exception("Export cleanup failed")
        record = db.query(ExportRequest).filter(ExportRequest.id == export_id, ExportRequest.company_id == company_id).with_for_update().first()
        if record:
            record.state = "FAILED"
            record.error = "Export could not complete. Narrow the filters or contact support."
            db.commit()


def expire_exports(db):
    while True:
        records = db.query(ExportRequest).filter(ExportRequest.expires_at <= datetime.utcnow()).limit(100).with_for_update(skip_locked=True).all()
        if not records:
            return
        for record in records:
            if record.storage_path:
                storage.delete_file(record.storage_path)
            db.delete(record)
        db.commit()
