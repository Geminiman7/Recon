import uuid
import enum

from sqlalchemy import Column, String, Float, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class ReconciliationStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    MISSING_IN_COMPANY = "MISSING_IN_COMPANY"
    MISSING_IN_PROCESSOR = "MISSING_IN_PROCESSOR"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    STATUS_MISMATCH = "STATUS_MISMATCH"
    DUPLICATE = "DUPLICATE"

class ReconciliationResult(Base):

    __tablename__ = "reconciliation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("reconciliation_jobs.id"), nullable=False)

    transaction_id = Column(String, nullable=False)

    company_amount = Column(Float)
    processor_amount = Column(Float)

    company_status = Column(String)
    processor_status = Column(String)

    status = Column(Enum(ReconciliationStatus), nullable=False)

Index("ix_results_tenant_job_order", ReconciliationResult.company_id, ReconciliationResult.job_id, ReconciliationResult.transaction_id, ReconciliationResult.id)
Index("ix_results_tenant_job_status", ReconciliationResult.company_id, ReconciliationResult.job_id, ReconciliationResult.status)
