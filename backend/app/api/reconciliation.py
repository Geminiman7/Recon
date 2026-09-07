from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api.dependencies import require_permission, get_current_user
from app.core.database import get_db
from app.models.export_request import ExportRequest
from app.services.reconciliation_service import ReconciliationService
from app.services.result_service import paginated_results
from app.services.export_service import create_export
from app.services.export_writers import MIME, EXTENSION
from app.services.storage_service import materialize

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post("/{job_id}/run")
def run(job_id: UUID, db: Session = Depends(get_db), current_user=Depends(require_permission("reconciliation:run"))):
    return ReconciliationService.enqueue(db, current_user.company_id, job_id, current_user.id)


@router.get("/{job_id}/results")
def results(job_id: UUID, page: int = Query(1, ge=1, le=100000), page_size: int = Query(50, ge=1, le=200),
            status: str | None = Query(None, max_length=40), search: str | None = Query(None, max_length=200),
            db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return paginated_results(db, current_user.company_id, job_id, page, page_size, status, search)


@router.post("/{job_id}/export/{format}", status_code=202)
def request_export(job_id: UUID, format: str, status: str | None = Query(None, max_length=40),
                   search: str | None = Query(None, max_length=200), db: Session = Depends(get_db),
                   current_user=Depends(require_permission("results:export"))):
    if format not in MIME:
        raise HTTPException(422, "Choose excel or pdf.")
    record = create_export(db, current_user, job_id, format, status, search)
    return {"id": str(record.id), "state": record.state, "expires_at": record.expires_at}


def owned_export(db, current_user, export_id):
    record = db.query(ExportRequest).filter(ExportRequest.id == export_id,
        ExportRequest.company_id == current_user.company_id, ExportRequest.user_id == current_user.id).first()
    if not record:
        raise HTTPException(404, "Export not found.")
    if record.expires_at <= datetime.utcnow():
        raise HTTPException(410, "Export expired. Request a new export.")
    return record


@router.get("/exports/{export_id}")
def export_status(export_id: UUID, db: Session = Depends(get_db), current_user=Depends(require_permission("results:export"))):
    record = owned_export(db, current_user, export_id)
    return {"id": str(record.id), "state": record.state, "error": record.error,
            "row_count": record.row_count, "expires_at": record.expires_at}


@router.get("/exports/{export_id}/download")
def download_export(export_id: UUID, db: Session = Depends(get_db), current_user=Depends(require_permission("results:export"))):
    record = owned_export(db, current_user, export_id)
    if record.state != "READY" or not record.storage_path:
        raise HTTPException(409, "Export is not ready.")
    reference, format = record.storage_path, record.format
    def chunks():
        with materialize(reference) as path:
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    yield chunk
    return StreamingResponse(chunks(), media_type=MIME[format], headers={"Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="reconciliation-{export_id}.{EXTENSION[format]}"'})
