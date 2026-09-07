import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ExportRequest(Base):
    __tablename__ = "export_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("reconciliation_jobs.id"), nullable=False)
    format = Column(String(8), nullable=False)
    filter_status = Column(String(40))
    search = Column(String(200))
    state = Column(String(16), nullable=False, default="PENDING")
    storage_path = Column(String(500))
    error = Column(String(200))
    row_count = Column(Integer)
    run_token = Column(String(36))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
