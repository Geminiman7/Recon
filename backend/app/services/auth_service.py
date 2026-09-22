import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User,UserRole
from app.models.password_reset_token import PasswordResetToken
from app.core.config import settings
from app.core.passwords import validate_password
from fastapi import HTTPException
from app.services.billing_service import BillingService

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
)


class AuthService:

    @staticmethod
    def request_password_reset(db: Session, email: str):
        user = db.query(User).filter(User.email == email).first()
        response = {"message": "If that email is registered, a password reset link has been sent."}
        if not user:
            return response

        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used.is_(False),
        ).update({PasswordResetToken.used: True})
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        ))
        db.commit()

        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        if settings.SMTP_HOST and settings.SMTP_FROM_EMAIL:
            message = EmailMessage()
            message["Subject"] = "Reset your Recon password"
            message["From"] = settings.SMTP_FROM_EMAIL
            message["To"] = user.email
            message.set_content(
                f"Use this link to reset your password (valid for {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n{reset_url}"
            )
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
                smtp.send_message(message)
        elif not settings.is_production:
            response["reset_url"] = reset_url
        return response

    @staticmethod
    def reset_password(db: Session, token: str, password: str):
        validate_password(password)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used.is_(False),
            PasswordResetToken.expires_at > datetime.utcnow(),
        ).with_for_update().first()
        if not record:
            raise ValueError("This reset link is invalid or has expired.")
        user = db.query(User).filter(User.id == record.user_id).first()
        if not user:
            raise ValueError("This reset link is invalid or has expired.")
        user.password_hash = hash_password(password)
        user.session_version = User.session_version + 1
        record.used = True
        db.commit()
        return {"message": "Password reset successfully. You can now sign in."}

    @staticmethod
    def register_company(db: Session, data):

        company_exists = db.query(Company).filter(
            Company.company_email == data.company_email
        ).first()

        if company_exists:
            raise ValueError("Company already exists.")

        user_exists = db.query(User).filter(
            User.email == data.admin_email
        ).first()

        if user_exists:
            raise ValueError("Administrator email already exists.")

        company = Company(
            company_name=data.company_name,
            company_email=data.company_email,
            phone=data.phone,
            address=data.address
        )

        db.add(company)
        db.flush()

        admin = User(
            company_id=company.id,
            full_name=data.admin_name,
            email=data.admin_email,
            password_hash=hash_password(data.password),
            role=UserRole.ADMIN
        )

        db.add(admin)

        # Each company receives one full-access, company-level trial.
        BillingService.ensure_trial(db, company.id)

        db.commit()
        db.refresh(company)

        return {
            "message": "Company registered successfully.",
            "company_id": str(company.id)
        }

    @staticmethod
    def login(db: Session, request):
        user = db.query(User).filter(
            User.email == request.email
        ).first()

        if not user or not user.is_active or not verify_password(request.password, user.password_hash):
            raise HTTPException(401, "Invalid email or password.")

        token = create_access_token(
            {
                "sub": str(user.id),
                "ver": user.session_version,
                "email": user.email,
                "company_id": str(user.company_id),
                "role": user.role
            }
        )

        return {
            "access_token": token,
            "token_type": "Bearer"
        }

