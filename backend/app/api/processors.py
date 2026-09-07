from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.schemas.processor import CreateProcessorRequest, ProcessorResponse
from app.services.processor_service import ProcessorService
from app.models.user import UserRole

router = APIRouter(
    prefix="/processors",
    tags=["Processors"]
)


@router.post("/", response_model=ProcessorResponse)
def create_processor(
    request: CreateProcessorRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Administrators can create processors.")

    try:
        return ProcessorService.create_processor(db, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ProcessorResponse])
def list_processors(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return ProcessorService.list_processors(db)
