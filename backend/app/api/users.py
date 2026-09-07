from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session
from uuid import UUID

from app.schemas.user import CreateUserRequest, UserResponse
from app.models.user import User, UserRole

from app.services.user_service import UserService

from app.core.database import get_db
from app.api.dependencies import get_current_user


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post("/", response_model=UserResponse)
def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    # role is stored as a UserRole enum on the ORM model
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only Administrators can create users."
        )

    return UserService.create_user(
        db,
        current_user,
        request
    )


@router.get("/", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    users = db.query(User).filter(
        User.company_id == current_user.company_id
    ).all()

    return users


@router.delete("/{user_id}")
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Administrators can delete users.")

    try:
        return UserService.delete_user(db, current_user, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{user_id}/active", response_model=UserResponse)
def set_user_active(
    user_id: UUID,
    active: bool,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Administrators can update users.")

    try:
        return UserService.set_active(db, current_user, user_id, active)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))