import uuid
import enum

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean, Integer
from sqlalchemy import ForeignKey
from sqlalchemy import Enum

from sqlalchemy.orm import relationship

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "Admin"
    FINANCE = "Finance"
    AUDITOR = "Auditor"
    VIEWER = "Viewer"


class User(Base):

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id"),
        nullable=False
    )

    full_name = Column(
        String,
        nullable=False
    )

    email = Column(
        String,
        unique=True,
        nullable=False
    )

    password_hash = Column(
        String,
        nullable=False
    )

    role = Column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.ADMIN
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    session_version = Column(Integer, nullable=False, default=0, server_default="0")

    company = relationship(
        "Company",
        back_populates="users"
    )