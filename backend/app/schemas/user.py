from app.core.passwords import Password
from uuid import UUID
from pydantic import BaseModel
from pydantic import EmailStr


class RegisterUser(BaseModel):

    company_name: str

    full_name: str

    email: EmailStr

    password: Password


class LoginUser(BaseModel):

    email: EmailStr

    password: Password


class CreateUserRequest(BaseModel):

    full_name: str

    email: EmailStr

    password: Password

    role: str


class UserResponse(BaseModel):

    id: UUID

    full_name: str

    email: EmailStr

    role: str

    is_active: bool

    class Config:
        from_attributes = True