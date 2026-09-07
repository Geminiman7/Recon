from fastapi import Request
from app.core.sessions import SESSION_COOKIE
from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from uuid import UUID

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.user import UserRole
from app.services.billing_service import BillingService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Sign in is required.")
    try:

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token."
            )

        try:
            user_id = UUID(user_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=401,
                detail="Invalid token."
            )

        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="User not found."
            )

        if not user.is_active or payload.get("ver") != user.session_version:
            raise HTTPException(401, "Your session has expired. Sign in again.")
        return user

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials."
        )


PERMISSIONS = {
    "jobs:create": {UserRole.ADMIN, UserRole.FINANCE},
    "jobs:delete": {UserRole.ADMIN},
    "uploads:create": {UserRole.ADMIN, UserRole.FINANCE},
    "reconciliation:run": {UserRole.ADMIN, UserRole.FINANCE},
    "users:manage": {UserRole.ADMIN},
    "results:export": {UserRole.ADMIN, UserRole.FINANCE, UserRole.AUDITOR},
}


def require_active_subscription(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _, _, access = BillingService.entitlement(db, current_user.company_id)
    if not access:
        raise HTTPException(status_code=402, detail="Your trial has ended or your subscription requires payment.")
    return current_user


def require_permission(permission: str):
    def checker(current_user=Depends(require_active_subscription)):
        if current_user.role not in PERMISSIONS.get(permission, set()):
            raise HTTPException(status_code=403, detail="You do not have permission for this action.")
        return current_user
    return checker
