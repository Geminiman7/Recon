from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import get_current_user, require_permission
from app.models.column_mapping import ColumnMapping
from app.models.job import JobStatus, ReconciliationJob
from app.models.upload import Upload, UploadType

router = APIRouter()


@router.post("/mapping")
def save_mapping(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_permission("reconciliation:run"))):
    try:
        if not payload or "job_id" not in payload:
            raise HTTPException(status_code=400, detail="Missing job_id in mapping payload.")

        job_id = UUID(str(payload["job_id"]))
        company_file_id = UUID(str(payload.get("company_file_id")))
        processor_file_ids = payload.get("processor_file_ids") or [payload.get("processor_file_id")]
        processor_file_ids = [UUID(str(file_id)) for file_id in processor_file_ids if file_id]
        if not processor_file_ids:
            raise HTTPException(status_code=400, detail="Select at least one processor file.")

        company_mapping = payload.get("company") or {}
        processor_mappings = payload.get("processors") or {}
        # Backwards-compatible single-file payload.
        if not processor_mappings and payload.get("processor_file_id"):
            processor_mappings[str(payload["processor_file_id"])] = payload.get("processor") or {}
        required_fields = ("transaction_id", "amount", "status")

        for side, mapping in (("company", company_mapping),):
            missing = [field for field in required_fields if not mapping.get(field)]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required {side} mappings: {', '.join(missing)}."
                )

        job = db.query(ReconciliationJob).filter(
            ReconciliationJob.id == job_id,
            ReconciliationJob.company_id == current_user.company_id
        ).with_for_update().first()
        if not job:
            raise HTTPException(status_code=404, detail="Reconciliation job not found.")

        if job.status in {JobStatus.QUEUED, JobStatus.PROCESSING}:
            raise HTTPException(409, "Wait for reconciliation to finish before changing mappings.")

        company_upload = db.query(Upload).filter(
            Upload.id == company_file_id,
            Upload.job_id == job_id,
            Upload.company_id == current_user.company_id,
            Upload.upload_type == UploadType.COMPANY
        ).first()
        processor_uploads = db.query(Upload).filter(
            Upload.id.in_(processor_file_ids), Upload.job_id == job_id,
            Upload.company_id == current_user.company_id, Upload.upload_type == UploadType.PROCESSOR
        ).all()
        if not company_upload or len(processor_uploads) != len(processor_file_ids) or any(not upload.processor_id for upload in processor_uploads):
            raise HTTPException(status_code=400, detail="Select valid company and processor files for this job.")
        for upload in processor_uploads:
            mapping = processor_mappings.get(str(upload.id)) or {}
            missing = [field for field in required_fields if not mapping.get(field)]
            if missing:
                raise HTTPException(status_code=400, detail=f"Missing required processor mappings for {upload.original_filename}: {', '.join(missing)}.")

        db.query(ColumnMapping).filter(
            ColumnMapping.company_id == current_user.company_id,
            ColumnMapping.job_id == job_id
        ).delete(synchronize_session=False)

        for processor_upload in processor_uploads:
            processor_mapping = processor_mappings[str(processor_upload.id)]
            for canonical_column in ("transaction_id", "amount", "status", "date", "reference"):
                company_column = company_mapping.get(canonical_column)
                processor_column = processor_mapping.get(canonical_column)
                if company_column and processor_column:
                    db.add(ColumnMapping(company_id=current_user.company_id, job_id=job_id,
                        processor_id=processor_upload.processor_id, processor_upload_id=processor_upload.id, company_column=company_column,
                        processor_column=processor_column, canonical_column=canonical_column))

        job.status = JobStatus.READY_TO_RECONCILE
        db.commit()

        return {
            "status": "ok",
            "mapping_state": "COMPLETE",
            "job_status": job.status.value,
            "message": (
                "Mapping complete. Column mappings are now the configured "
                "basis for reconciliation until they are edited or reset."
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise
