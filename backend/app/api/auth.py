import logging
from fastapi import Request, Response
from app.core.sessions import SESSION_COOKIE, issue_csrf, set_session, clear_session
from app.core.throttling import throttle
from app.core.config import settings
from app.models.user import User
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.company import CompanyRegistration
from app.services.auth_service import AuthService
from app.schemas.user import UserResponse
from app.api.dependencies import get_current_user
from app.schemas.auth import LoginRequest, PasswordResetConfirm, PasswordResetRequest
from app.services.billing_service import BillingService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/register")
def register_company(
    request: CompanyRegistration,
    db: Session = Depends(get_db)
):

    try:
        return AuthService.register_company(
            db,
            request
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/login")
def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):

    throttle("account", request.email.lower(), settings.LOGIN_ACCOUNT_LIMIT, 900)
    try:

        result = AuthService.login(db, request)
        set_session(response, result["access_token"])
        return {"message": "Signed in successfully."}

    except ValueError as e:

        raise HTTPException(
            status_code=401,
            detail=str(e)
        )


@router.post("/forgot-password")
def forgot_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    try:
        return AuthService.request_password_reset(db, request.email)
    except Exception:
        logging.getLogger("recon").exception("Password reset delivery failed")
        # Do not disclose whether the address exists or expose mail-provider errors.
        return {"message": "If that email is registered, a password reset link has been sent."}


@router.post("/reset-password")
def reset_password(request: PasswordResetConfirm, db: Session = Depends(get_db)):
    try:
        return AuthService.reset_password(db, request.token, request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/me")
def me(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # The subscription is derived from the database on every request, not JWT claims.
    # This keeps access correct after expiry, payment failure, or renewal.
    
    response = {
        "id": str(current_user.id),
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
        "is_active": current_user.is_active,
    }
    response["subscription"] = BillingService.serialize_entitlement(db, current_user.company_id)
    return response


@router.get("/csrf")
def csrf(request: Request, response: Response):
    return {"csrf_token": issue_csrf(response, request.cookies.get(SESSION_COOKIE, ""))}


@router.post("/logout")
def logout(response: Response, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    current_user.session_version = User.session_version + 1
    db.commit()
    clear_session(response)
    return {"message": "Signed out."}
