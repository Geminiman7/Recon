from fastapi import HTTPException
from sqlalchemy import func
from app.models.job import ReconciliationJob
from app.models.reconciliation_result import ReconciliationResult as Result, ReconciliationStatus as Status


def owned_job(db, company_id, job_id):
    job = db.query(ReconciliationJob).filter(ReconciliationJob.id == job_id,
        ReconciliationJob.company_id == company_id).first()
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


def result_query(db, company_id, job_id, status=None, search=None):
    query = db.query(Result).filter(Result.company_id == company_id, Result.job_id == job_id)
    if status:
        if status.upper() == "MISSING":
            query = query.filter(Result.status.in_([Status.MISSING_IN_COMPANY, Status.MISSING_IN_PROCESSOR]))
        else:
            try:
                normalized = Status(status.upper())
            except ValueError as exc:
                raise HTTPException(422, "Invalid result status.") from exc
            query = query.filter(Result.status == normalized)
    if search and search.strip():
        literal = search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        query = query.filter(Result.transaction_id.ilike(f"%{literal}%", escape="!"))
    return query


def serialize_result(row):
    difference = row.processor_amount - row.company_amount if row.company_amount is not None and row.processor_amount is not None else None
    return {"id": str(row.id), "transaction_id": row.transaction_id, "company_amount": row.company_amount,
        "processor_amount": row.processor_amount, "difference": difference,
        "company_status": row.company_status, "processor_status": row.processor_status, "status": row.status.value}


def paginated_results(db, company_id, job_id, page=1, page_size=50, status=None, search=None):
    owned_job(db, company_id, job_id)
    query = result_query(db, company_id, job_id, status, search)
    total = query.count()
    counts = dict(result_query(db, company_id, job_id).with_entities(Result.status, func.count(Result.id)).group_by(Result.status).all())
    rows = query.order_by(Result.transaction_id, Result.id).offset((page - 1) * page_size).limit(page_size).all()
    return {"results": [serialize_result(row) for row in rows], "page": page, "page_size": page_size,
        "filtered_total": total, "total_pages": (total + page_size - 1) // page_size,
        "total": sum(counts.values()), "matched": counts.get(Status.MATCHED, 0),
        "mismatched": sum(counts.get(s, 0) for s in [Status.AMOUNT_MISMATCH, Status.STATUS_MISMATCH, Status.DUPLICATE]),
        "duplicates": counts.get(Status.DUPLICATE, 0),
        "missing": sum(counts.get(s, 0) for s in [Status.MISSING_IN_COMPANY, Status.MISSING_IN_PROCESSOR])}
