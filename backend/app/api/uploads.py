from uuid import UUID

from fastapi import APIRouter
from fastapi import UploadFile
from fastapi import File
from fastapi import Depends
from fastapi import Form
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.header_service import HeaderService
from app.services.upload_service import UploadService

from app.api.dependencies import get_current_user, require_permission
from app.schemas.upload import UploadResponse
from app.models.upload import Upload
from app.models.processor import Processor

router = APIRouter(
    prefix="/uploads",
    tags=["Uploads"]
)


@router.post("/company", response_model=UploadResponse)
async def upload_company_file(

    job_id: UUID = Form(...),

    file: UploadFile = File(...),

    db: Session = Depends(get_db),

    current_user=Depends(require_permission("uploads:create"))

):

    return await UploadService.upload_company(
        db,
        current_user,
        job_id,
        file
    )

@router.post("/processor", response_model=UploadResponse)
async def upload_processor_file(

    job_id: UUID = Form(...),

    processor_id: UUID = Form(...),

    file: UploadFile = File(...),

    db: Session = Depends(get_db),

    current_user=Depends(require_permission("uploads:create"))

):

    return await UploadService.upload_processor(
        db,
        current_user,
        job_id,
        processor_id,
        file
    )



@router.get('', response_model=list[UploadResponse])
@router.get('/', response_model=list[UploadResponse], include_in_schema=False)
def list_uploads(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    uploads = db.query(Upload).filter(
        Upload.company_id == current_user.company_id
    ).order_by(Upload.uploaded_at.desc(), Upload.id.desc()).all()

    return uploads


@router.get('/{upload_id}/columns')
def get_upload_columns(
    upload_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("uploads:create"))
):

    upload = db.query(Upload).filter(
        Upload.id == upload_id,
        Upload.company_id == current_user.company_id
    ).first()

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    try:
        return {"columns": HeaderService.read_headers(upload.storage_path)}
    except FileNotFoundError as error:
        raise HTTPException(410,
            "The stored file is missing. Restore it from backup, or create a new job "
            "and upload the original files again.") from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Unable to read file headers. Check the file format and limits."
        )


@router.get('/processors')
def list_processors(
    db: Session = Depends(get_db)
):

    processors = db.query(Processor).filter(Processor.is_active == True).all()

    return [
        {
            "id": str(processor.id),
            "name": processor.name,
            "description": processor.description,
        }
        for processor in processors
    ]


@router.get('/job/{job_id}', response_model=list[UploadResponse])
def list_job_uploads(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("uploads:create"))
):

    uploads = db.query(Upload).filter(
        Upload.job_id == job_id,
        Upload.company_id == current_user.company_id
    ).all()

    return uploads
