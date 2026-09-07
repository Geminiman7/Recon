import hashlib
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
from starlette.concurrency import run_in_threadpool
from fastapi import HTTPException
from app.core.config import ALLOWED_EXTENSIONS, settings
from app.models.job import ReconciliationJob, JobStatus
from app.models.upload import Upload, UploadStatus, UploadType
from app.models.processor import Processor
from app.services.file_validation import validate_file
from app.services import storage_service as storage

class UploadService:
    @staticmethod
    def validate_job(db, company_id, job_id):
        job = db.query(ReconciliationJob).filter(ReconciliationJob.id == job_id,
            ReconciliationJob.company_id == company_id).with_for_update().first()
        if not job:
            raise HTTPException(404, "Job not found.")
        if job.status in {JobStatus.QUEUED, JobStatus.PROCESSING}:
            raise HTTPException(409, "Wait for reconciliation to finish before uploading.")
        return job

    @staticmethod
    async def save_upload(db, current_user, job_id, file, upload_type, processor_id=None):
        extension = Path(file.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(422, "Unsupported file type.")
        with NamedTemporaryFile(suffix=extension, delete=False) as temporary:
            path = Path(temporary.name)
        reference = None
        committed = False
        try:
            size = 0
            digest = hashlib.sha256()
            with path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.MAX_FILE_BYTES:
                        raise HTTPException(413, "File exceeds the upload size limit.")
                    digest.update(chunk)
                    output.write(chunk)
            try:
                await run_in_threadpool(validate_file, path)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            UploadService.validate_job(db, current_user.company_id, job_id)
            if processor_id and not db.query(Processor).filter(Processor.id == processor_id, Processor.is_active.is_(True)).first():
                raise HTTPException(404, "Processor not found.")
            checksum = digest.hexdigest()
            if db.query(Upload).filter(Upload.company_id == current_user.company_id,
                    Upload.job_id == job_id, Upload.checksum == checksum).first():
                raise HTTPException(409, "Duplicate file uploaded.")
            filename = f"{uuid4()}{extension}"
            reference = await run_in_threadpool(storage.put_file, path,
                f"uploads/{current_user.company_id}/{job_id}/{filename}")
            record = Upload(company_id=current_user.company_id, job_id=job_id, processor_id=processor_id,
                uploaded_by=current_user.id, original_filename=Path(file.filename).name,
                stored_filename=filename, storage_path=reference, checksum=checksum,
                mime_type=file.content_type or "application/octet-stream", file_size=size,
                upload_type=upload_type, status=UploadStatus.UPLOADED)
            db.add(record)
            db.commit()
            committed = True
            db.refresh(record)
            return record
        except Exception:
            db.rollback()
            if reference and not committed:
                try:
                    await run_in_threadpool(storage.delete_file, reference)
                except Exception:
                    logging.getLogger("recon").exception("Could not clean up failed upload")
            raise
        finally:
            path.unlink(missing_ok=True)
            await file.close()

    @staticmethod
    async def upload_company(db, current_user, job_id, file):
        return await UploadService.save_upload(db, current_user, job_id, file, UploadType.COMPANY)

    @staticmethod
    async def upload_processor(db, current_user, job_id, processor_id, file):
        return await UploadService.save_upload(db, current_user, job_id, file, UploadType.PROCESSOR, processor_id)
