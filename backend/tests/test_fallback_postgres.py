"""Optional real PostgreSQL concurrency test in a disposable isolated schema."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "Set TEST_POSTGRES_URL for PostgreSQL integration")
class PostgresFallbackTests(unittest.TestCase):
    def test_concurrent_claims_and_shared_rate_limits(self):
        from app.main import app  # Register application models.
        from app.core.database import Base
        from app.core.throttling import throttle
        from app.models.company import Company
        from app.models.user import User, UserRole
        from app.models.job import ReconciliationJob, JobStatus
        from app.workers.fallback_worker import consume_once
        from app.services.reconciliation_service import ReconciliationService

        schema = "fallback_test_" + uuid4().hex
        admin = create_engine(os.environ["TEST_POSTGRES_URL"])
        engine = None
        try:
            with admin.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            engine = create_engine(os.environ["TEST_POSTGRES_URL"],
                connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5})
            Base.metadata.create_all(engine)
            sessions = sessionmaker(bind=engine, expire_on_commit=False)
            with sessions() as db:
                company = Company(company_name="Test", company_email="test@example.com")
                db.add(company)
                db.flush()
                user = User(company_id=company.id, email="test@example.com", full_name="Test",
                    password_hash="unused", role=UserRole.ADMIN)
                db.add(user)
                db.flush()
                job = ReconciliationJob(company_id=company.id, created_by=user.id, job_name="Test",
                    run_token=str(uuid4()), queued_at=datetime.utcnow(), status=JobStatus.QUEUED)
                db.add(job)
                db.commit()
                job_id = job.id

            with patch("app.workers.fallback_worker.SessionLocal", sessions):
                with sessions() as owner:
                    locked = owner.query(ReconciliationJob).filter_by(id=job_id).with_for_update().one()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        self.assertFalse(pool.submit(consume_once, False).result(timeout=5))
                    locked.status = JobStatus.PROCESSING
                    owner.flush()
                    owner.rollback()  # Simulates the transaction lost on process death.

                def complete(db, company_id, job_id, actor, token):
                    row = db.get(ReconciliationJob, job_id)
                    row.status = JobStatus.COMPLETED
                    db.commit()

                with patch.object(ReconciliationService, "run", side_effect=complete) as run:
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futures = [pool.submit(consume_once, False) for _ in range(2)]
                        self.assertEqual(sum(f.result(timeout=5) for f in futures), 1)
                    run.assert_called_once()

            def attempt(_):
                try:
                    throttle("test", "shared", 5, window=3600)
                    return 200
                except HTTPException as exc:
                    return exc.status_code

            with patch("app.core.throttling.SessionLocal", sessions):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    statuses = list(pool.map(attempt, range(20)))
                self.assertEqual(statuses.count(200), 5)
                self.assertEqual(statuses.count(429), 15)
        finally:
            if engine:
                engine.dispose()
            # Only the generated test schema is removed, never application data.
            assert schema.startswith("fallback_test_") and len(schema) == 46
            with admin.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            admin.dispose()
