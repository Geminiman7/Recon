import os
os.environ.update(DATABASE_URL="sqlite://", SECRET_KEY="test-only-secret-with-at-least-32-bytes", ENVIRONMENT="test", REDIS_URL="", SENTRY_DSN="")

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4
import redis
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app, health_ready
from app.core.database import Base
from app.core.config import settings, Settings
from app.core.redis_health import RedisCircuit, publish
from app.models.company import Company
from app.models.user import User, UserRole
from app.models.job import ReconciliationJob, JobStatus
from app.models.resilience import WorkerHeartbeat
from app.models.export_request import ExportRequest
from app.services.reconciliation_service import ReconciliationService
from app.workers.fallback_worker import consume_once


class CircuitTests(unittest.TestCase):
    def test_production_without_redis(self):
        for redis_url in (None, "", "   "):
            configured = Settings(_env_file=None, ENVIRONMENT="production",
                SECRET_KEY="test-only-secret-with-at-least-32-bytes",
                FRONTEND_URL="https://example.com", STORAGE_BACKEND="s3",
                S3_BUCKET="test-bucket", REDIS_URL=redis_url)
            self.assertIsNone(configured.REDIS_URL)
        with self.assertRaisesRegex(RuntimeError, "HTTPS FRONTEND_URL"):
            Settings(_env_file=None, ENVIRONMENT="production",
                SECRET_KEY="test-only-secret-with-at-least-32-bytes",
                FRONTEND_URL="http://example.com", STORAGE_BACKEND="s3",
                S3_BUCKET="test-bucket", REDIS_URL=None)

    def test_no_redis_skips_client_and_publish(self):
        circuit = RedisCircuit()
        task = Mock()
        with patch.object(settings, "REDIS_URL", None), patch("app.core.redis_health.redis.from_url") as connect, patch("app.core.redis_health.circuit", circuit):
            self.assertFalse(publish(task, "job"))
            self.assertEqual(circuit.state, "disabled")
            connect.assert_not_called()
            task.apply_async.assert_not_called()

    def test_outage_cooldown_and_stable_recovery(self):
        circuit = RedisCircuit()
        circuit.client = Mock()
        circuit.client.ping.side_effect = redis.ConnectionError("offline")
        with patch.object(settings, "REDIS_URL", "redis://test"), patch("app.core.redis_health.time.monotonic", return_value=0) as clock:
            self.assertFalse(circuit.available())
            self.assertFalse(circuit.available())
            self.assertEqual(circuit.client.ping.call_count, 1)
            circuit.client.ping.side_effect = None
            clock.return_value = settings.REDIS_PROBE_INTERVAL
            self.assertFalse(circuit.available())
            self.assertEqual(circuit.state, "half_open")
            clock.return_value += settings.REDIS_PROBE_INTERVAL
            self.assertTrue(circuit.available())
            circuit.failed()
            self.assertFalse(circuit.available())

    def test_ambiguous_publish_keeps_work_durable(self):
        task = Mock()
        task.apply_async.side_effect = redis.ConnectionError("reply lost")
        with patch("app.core.redis_health.circuit") as circuit:
            circuit.available.return_value = True
            self.assertFalse(publish(task, "id"))
            circuit.failed.assert_called_once()
            self.assertFalse(task.apply_async.call_args.kwargs["retry"])


class FallbackTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        company = Company(company_name="Test", company_email="test@example.com")
        self.db.add(company)
        self.db.flush()
        user = User(company_id=company.id, email="test@example.com", full_name="Test", password_hash="test", role=UserRole.ADMIN)
        self.db.add(user)
        self.db.flush()
        self.job = ReconciliationJob(company_id=company.id, created_by=user.id, job_name="Test",
            status=JobStatus.QUEUED, run_token=str(uuid4()), queued_by=user.id, queued_at=datetime.utcnow())
        self.db.add(self.job)
        self.db.commit()
        sessions = patch("app.workers.fallback_worker.SessionLocal", self.Session)
        sessions.start()
        self.addCleanup(sessions.stop)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def complete(self, db, company_id, job_id, user_id, token):
        job = db.get(ReconciliationJob, job_id)
        self.assertEqual(token, job.run_token)
        self.assertEqual(user_id, job.queued_by)
        job.status = JobStatus.COMPLETED
        db.commit()

    def test_outage_drains_queue_and_no_duplicate_processing(self):
        with patch.object(ReconciliationService, "run", side_effect=self.complete) as run:
            self.assertTrue(consume_once(False))
            self.assertFalse(consume_once(False))
            run.assert_called_once()
        self.db.refresh(self.job)
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        self.assertEqual(ReconciliationService.run(self.db, self.job.company_id, self.job.id,
            self.job.queued_by, self.job.run_token)["result_state"], "COMPLETED")

    def test_healthy_broker_grace_and_lost_message_recovery(self):
        with patch.object(ReconciliationService, "run", side_effect=self.complete) as run:
            self.assertFalse(consume_once(True))
            run.assert_not_called()
            self.job.queued_at = datetime.utcnow() - timedelta(seconds=settings.FALLBACK_GRACE_SECONDS + 1)
            self.db.commit()
            self.assertTrue(consume_once(True))
            run.assert_called_once()

    def test_failed_work_does_not_poison_queue_or_replay(self):
        with patch.object(ReconciliationService, "run", side_effect=ValueError("bad input")):
            self.assertTrue(consume_once(False))
        self.db.refresh(self.job)
        self.assertEqual(self.job.status, JobStatus.FAILED)
        self.assertFalse(consume_once(False))
        self.assertEqual(ReconciliationService.run(self.db, self.job.company_id, self.job.id,
            self.job.queued_by, self.job.run_token)["result_state"], "FAILED")

    def test_database_disconnect_leaves_job_queued(self):
        from sqlalchemy.exc import OperationalError
        with patch.object(ReconciliationService, "run", side_effect=OperationalError("offline", {}, None)):
            with self.assertRaises(OperationalError):
                consume_once(False)
        self.db.refresh(self.job)
        self.assertEqual(self.job.status, JobStatus.QUEUED)

    def test_stale_run_token_cannot_replace_current_results(self):
        with self.assertRaises(HTTPException) as failure:
            ReconciliationService.run(self.db, self.job.company_id, self.job.id, self.job.queued_by, "old-token")
        self.assertEqual(failure.exception.status_code, 409)
        self.assertEqual(self.job.status, JobStatus.QUEUED)

    def test_exports_continue_during_outage(self):
        self.job.status = JobStatus.COMPLETED
        record = ExportRequest(company_id=self.job.company_id, user_id=self.job.created_by, job_id=self.job.id,
            format="excel", run_token=self.job.run_token, expires_at=datetime.utcnow() + timedelta(hours=1))
        self.db.add(record)
        self.db.commit()
        with patch("app.workers.fallback_worker.generate_export") as generate:
            self.assertTrue(consume_once(False))
            self.assertEqual(generate.call_args.args[1:], (record.id, record.company_id))

    def test_export_database_disconnect_preserves_pending_request(self):
        from sqlalchemy.exc import OperationalError
        from app.services.export_service import generate_export
        self.job.status = JobStatus.COMPLETED
        record = ExportRequest(company_id=self.job.company_id, user_id=self.job.created_by,
            job_id=self.job.id, format="excel", run_token=self.job.run_token,
            expires_at=datetime.utcnow() + timedelta(hours=1))
        self.db.add(record)
        self.db.commit()
        with patch("app.services.export_service.storage.put_file", side_effect=OperationalError("offline", {}, None)):
            with self.assertRaises(OperationalError):
                generate_export(self.db, record.id, record.company_id)
        self.db.refresh(record)
        self.assertEqual(record.state, "PENDING")

    def test_readiness_requires_live_fallback_during_outage(self):
        with patch.object(settings, "REDIS_URL", "redis://offline"), patch("app.core.redis_health.circuit.available", return_value=False):
            self.assertEqual(health_ready(self.db).status_code, 503)
            heartbeat = WorkerHeartbeat(worker_id=str(uuid4()), seen_at=datetime.utcnow())
            self.db.add(heartbeat)
            self.db.commit()
            response = health_ready(self.db)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"degraded", response.body)
            heartbeat.seen_at = datetime.utcnow() - timedelta(seconds=25)
            self.db.commit()
            self.assertEqual(health_ready(self.db).status_code, 503)

    def test_readiness_without_configured_redis(self):
        with patch.object(settings, "REDIS_URL", None), patch("app.main.celery_app.control.inspect") as inspect:
            self.assertEqual(health_ready(self.db).status_code, 503)
            self.db.add(WorkerHeartbeat(worker_id=str(uuid4()), seen_at=datetime.utcnow()))
            self.db.commit()
            response = health_ready(self.db)
            self.assertEqual(response.status_code, 200)
            import json
            payload = json.loads(response.body)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["checks"]["redis"], "disabled")
            self.assertEqual(payload["checks"]["celery"], "disabled")
            inspect.assert_not_called()
