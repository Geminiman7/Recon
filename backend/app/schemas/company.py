from app.core.passwords import Password
from pydantic import BaseModel, EmailStr


class CompanyRegistration(BaseModel):
    company_name: str
    company_email: EmailStr
    phone: str
    address: str

    admin_name: str
    admin_email: EmailStr
    password: Password