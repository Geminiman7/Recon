from uuid import UUID
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.export_service import generate_export, expire_exports


@celery_app.task
def build_export(export_id, company_id):
    with SessionLocal() as db:
        generate_export(db, UUID(export_id), UUID(company_id))


@celery_app.task
def cleanup_exports():
    with SessionLocal() as db:
        expire_exports(db)
