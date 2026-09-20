from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "recon",
    broker=settings.REDIS_URL or "redis://redis:6379/0",
    backend=settings.REDIS_URL or "redis://redis:6379/0",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=False,
    task_publish_retry=False,
    broker_connection_timeout=1,
    task_time_limit=30 * 60,
    task_soft_time_limit=29 * 60,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    broker_pool_limit=10,
    broker_transport_options={"visibility_timeout": 3600, "socket_timeout": 1,
        "socket_connect_timeout": 1, "retry_on_timeout": False, "max_retries": 0},
    result_expires=3600,
    task_ignore_result=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)

celery_app.conf.imports = ("app.workers.reconciliation_worker", "app.workers.export_worker")
celery_app.conf.beat_schedule = {"expire-exports": {"task": "app.workers.export_worker.cleanup_exports", "schedule": 3600.0}}

from celery.signals import worker_process_init

@worker_process_init.connect
def reset_worker_pool(**kwargs):
    from app.core.database import engine
    engine.dispose(close=False)

