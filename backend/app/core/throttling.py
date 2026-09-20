"""Shared durable rate limits: no reset or split counter on Redis recovery."""
import hashlib
import time
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import SessionLocal
from app.models.resilience import RateBucket


def throttle(scope: str, identity: str, limit: int, window: int = 60):
    from datetime import datetime
    digest = hashlib.sha256(identity.encode()).hexdigest()
    bucket = int(time.time()) // window
    key = f"recon:rate:{scope}:{digest}:{bucket}"
    try:
        with SessionLocal() as db:
            if db.bind.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert
            statement = insert(RateBucket).values(key=key, count=1,
                expires_at=datetime.utcfromtimestamp((bucket + 1) * window))
            statement = statement.on_conflict_do_update(
                index_elements=[RateBucket.key], set_={"count": RateBucket.count + 1}
            ).returning(RateBucket.count)
            count = db.execute(statement).scalar_one()
            db.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Sign-in is temporarily unavailable.",
            headers={"Retry-After": "30"}) from exc
    if count > limit:
        raise HTTPException(429, "Too many attempts. Try again later.",
            headers={"Retry-After": str(window)})
