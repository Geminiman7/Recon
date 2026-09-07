from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.core.security import hash_password


class UserService:

    @staticmethod
    def create_user(db, current_user, request):

        existing = db.query(User).filter(
            User.email == request.email
        ).first()

        if existing:
            raise ValueError("Email already exists.")

        user = User(
            company_id=current_user.company_id,
            full_name=request.full_name,
            email=request.email,
            password_hash=hash_password(request.password),
            role=UserRole(request.role)
        )

        db.add(user)

        db.commit()

        db.refresh(user)

        return user

    @staticmethod
    def delete_user(db, current_user, user_id):

        user = db.query(User).filter(
            User.id == user_id,
            User.company_id == current_user.company_id
        ).first()

        if not user:
            raise ValueError("User not found.")

        db.delete(user)
        db.commit()

        return {"message": "User deleted successfully."}

    @staticmethod
    def set_active(db, current_user, user_id, is_active: bool):

        user = db.query(User).filter(
            User.id == user_id,
            User.company_id == current_user.company_id
        ).first()

        if not user:
            raise ValueError("User not found.")

        if user.is_active != is_active:
            user.session_version = User.session_version + 1
        user.is_active = is_active
        db.commit()
        db.refresh(user)

        return user