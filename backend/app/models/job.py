import uuid
import enum

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Enum
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.sql import func

from sqlalchemy.orm import relationship

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    READY_FOR_MAPPING = "READY_FOR_MAPPING"
    MAPPING = "MAPPING"
    READY_TO_RECONCILE = "READY_TO_RECONCILE"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReconciliationJob(Base):

    __tablename__ = "reconciliation_jobs"

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

    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    job_name = Column(
        String(200),
        nullable=False
    )

    description = Column(
        String(1000)
    )

    status = Column(
        Enum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    run_token = Column(String(36), nullable=True)

    company = relationship("Company")
    creator = relationship("User")