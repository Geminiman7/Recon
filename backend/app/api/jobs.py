from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.schemas.job import (
    CreateJobRequest,
    JobResponse
)

from app.services.job_service import JobService, JobNotFoundException

from app.api.dependencies import get_current_user, require_permission

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


@router.post(
    "",
    response_model=JobResponse
)
def create_job(
    request: CreateJobRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("jobs:create"))
):

    try:

        return JobService.create_job(
            db,
            current_user,
            request
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@router.get(
    "",
    response_model=list[JobResponse]
)
def get_jobs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return JobService.get_company_jobs(
        db,
        current_user.company_id
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse
)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    job = JobService.get_job(
        db,
        current_user.company_id,
        job_id
    )

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Job not found."
        )

    return job


@router.delete("/{job_id}")
def delete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("jobs:delete"))
):

    try:
        return JobService.delete_job(
            db,
            current_user.company_id,
            job_id
        )
    except JobNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
