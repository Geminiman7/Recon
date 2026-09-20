from sqlalchemy.orm import Session
import pandas as pd

from app.models.upload import Upload, UploadType
from app.models.job import ReconciliationJob, JobStatus
from app.models.column_mapping import ColumnMapping
from app.models.reconciliation_result import ReconciliationResult, ReconciliationStatus

from app.services.dataframe_service import DataFrameService
from app.services.canonical_service import CanonicalService
from app.services.reconciliation_engine import ReconciliationEngine
from app.services.activity_service import ActivityService
from app.core.config import settings


class ReconciliationService:

    @staticmethod
    def load_upload(upload):
        from fastapi import HTTPException
        try:
            return DataFrameService.load_file(upload.storage_path)
        except FileNotFoundError as exc:
            raise HTTPException(422,
                f"The stored file '{upload.original_filename}' is missing. "
                "Restore it from backup, or create a new job, upload the original files again, "
                "and save the column mapping. Ask your administrator to check persistent storage.") from exc

    @staticmethod
    def apply_mapping(df, mappings, source):
        rename_map = {
            getattr(mapping, f"{source}_column").strip().lower().replace(" ", "_"): mapping.canonical_column
            for mapping in mappings
        }
        normalized_columns = {
            column: column.strip().lower().replace(" ", "_")
            for column in df.columns
        }
        return df.rename(columns=normalized_columns).rename(columns=rename_map)

    @staticmethod
    def run(db: Session, company_id, job_id, user_id=None, run_token=None):

        from fastapi import HTTPException
        job = db.query(ReconciliationJob).filter(ReconciliationJob.id == job_id,
            ReconciliationJob.company_id == company_id).with_for_update().first()
        if not job:
            raise HTTPException(404, "Job not found.")
        if not run_token or job.run_token != run_token:
            raise HTTPException(409, "Reconciliation attempt is no longer current.")
        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return {"result_state": job.status.value}
        job.status = JobStatus.PROCESSING
        db.flush()
        company_upload = (
            db.query(Upload)
            .filter(
                Upload.job_id == job_id,
                Upload.company_id == company_id,
                Upload.upload_type == UploadType.COMPANY
            )
            .first()
        )

        mapped_processor_file_ids = [
            row[0] for row in db.query(ColumnMapping.processor_upload_id).filter(
                ColumnMapping.company_id == company_id,
                ColumnMapping.job_id == job_id,
                ColumnMapping.processor_upload_id.isnot(None),
            ).distinct().all()
        ]
        processor_uploads = (
            db.query(Upload)
            .filter(
                Upload.job_id == job_id,
                Upload.company_id == company_id,
                Upload.upload_type == UploadType.PROCESSOR,
                Upload.id.in_(mapped_processor_file_ids)
            )
            .all()
        )

        if not company_upload or not processor_uploads:
            raise ValueError("Both company and processor files are required.")


        company_source_df = ReconciliationService.load_upload(company_upload)
        company_df = None
        processor_frames = []
        for processor_upload in processor_uploads:
            mappings = db.query(ColumnMapping).filter(
                ColumnMapping.company_id == company_id,
                ColumnMapping.job_id == job_id,
                ColumnMapping.processor_upload_id == processor_upload.id
            ).all()
            if not mappings:
                raise ValueError(f"No column mapping has been saved for processor file '{processor_upload.original_filename}'.")

            mapped_company_df = ReconciliationService.apply_mapping(
                company_source_df.copy(), mappings, "company")
            processor_df = ReconciliationService.apply_mapping(
                ReconciliationService.load_upload(processor_upload), mappings, "processor")
            mapped_company_df = CanonicalService.prepare(mapped_company_df)
            processor_df = CanonicalService.prepare(processor_df)

            if company_df is None:
                company_df = mapped_company_df
            elif not company_df.equals(mapped_company_df):
                raise ValueError(
                    "Company column mappings differ between selected processor files. "
                    "Use the same company mappings for every processor file."
                )

            processor_df = processor_df.copy()
            processor_df["processor_upload_id"] = str(processor_upload.id)
            processor_df["processor_id"] = str(processor_upload.processor_id)
            processor_frames.append(processor_df)

        combined_processor_df = pd.concat(processor_frames, ignore_index=True, sort=False)
        results = ReconciliationEngine.reconcile(company_df, combined_processor_df)

        db.query(ReconciliationResult).filter(
            ReconciliationResult.company_id == company_id,
            ReconciliationResult.job_id == job_id,
        ).delete(synchronize_session=False)

        objects = []
        for row in results:
            objects.append(ReconciliationResult( company_id=company_id, job_id=job_id, transaction_id=row["transaction_id"], company_amount=row["company_amount"], processor_amount=row["processor_amount"], company_status=row["company_status"], processor_status=row["processor_status"], status=row["status"] ))

        db.bulk_save_objects(objects)
        from datetime import datetime
        job.completed_at = datetime.utcnow()
        job.status = JobStatus.COMPLETED
        ActivityService.audit(db, company_id, user_id, "reconciliation.completed", "reconciliation_job", job_id, {"results": len(results)})
        ActivityService.notify(db, company_id, "Reconciliation ready for review", f"{job.job_name} has refreshed results to validate.", "success", user_id)
        db.commit()

        matched = sum(row["status"] == ReconciliationStatus.MATCHED for row in results)
        mismatched = sum(
            row["status"] in {
                ReconciliationStatus.AMOUNT_MISMATCH,
                ReconciliationStatus.STATUS_MISMATCH,
                ReconciliationStatus.DUPLICATE,
            }
            for row in results
        )
        missing = sum(
            row["status"] in {
                ReconciliationStatus.MISSING_IN_COMPANY,
                ReconciliationStatus.MISSING_IN_PROCESSOR,
            }
            for row in results
        )

        return {
            "message": "Reconciliation refreshed. Review and validate the latest results.",
            "result_state": "READY_FOR_VALIDATION",
            "mapping_state": "COMPLETE",
            "total": len(results),
            "matched": matched,
            "mismatched": mismatched,
            "missing": missing,
        }

    @staticmethod
    def enqueue(db: Session, company_id, job_id, user_id=None):
        from uuid import uuid4
        from fastapi import HTTPException
        job = db.query(ReconciliationJob).filter(ReconciliationJob.id == job_id,
            ReconciliationJob.company_id == company_id).with_for_update().first()
        if not job:
            raise HTTPException(404, "Job not found.")
        if job.status in {JobStatus.QUEUED, JobStatus.PROCESSING}:
            raise HTTPException(409, "Job is already queued or processing.")
        run_token = str(uuid4())
        job.run_token = run_token
        job.status = JobStatus.QUEUED
        job.completed_at = None
        from datetime import datetime
        job.queued_at = datetime.utcnow()
        job.queued_by = user_id
        db.commit()
        try:
            if settings.RECONCILIATION_MODE.lower() == "async":
                from app.workers.reconciliation_worker import run_reconciliation_task
                from app.core.redis_health import publish
                publish(run_reconciliation_task, str(company_id), str(job_id), str(user_id) if user_id else None, run_token)
            else:
                return ReconciliationService.run(db, company_id, job_id, user_id, run_token)
        except Exception:
            db.rollback()
            db.query(ReconciliationJob).filter(ReconciliationJob.id == job_id,
                ReconciliationJob.company_id == company_id, ReconciliationJob.run_token == run_token,
                ReconciliationJob.status == JobStatus.QUEUED).update({"status": JobStatus.FAILED})
            db.commit()
            raise
        return {"message": "Reconciliation queued.", "result_state": "QUEUED", "job_id": str(job_id)}
