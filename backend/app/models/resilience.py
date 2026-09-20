from sqlalchemy import Column, String, Integer, DateTime
from app.core.database import Base


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key = Column(String(160), primary_key=True)
    count = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    worker_id = Column(String(36), primary_key=True)
    seen_at = Column(DateTime, nullable=False)
