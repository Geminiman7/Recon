import pandas as pd

from app.models.reconciliation_result import ReconciliationStatus

class ReconciliationEngine:

    @staticmethod
    def reconcile(company_df: pd.DataFrame, processor_df: pd.DataFrame):
        company_duplicates = set(company_df.loc[company_df.duplicated("transaction_id", keep=False), "transaction_id"])
        processor_duplicates = set(processor_df.loc[processor_df.duplicated("transaction_id", keep=False), "transaction_id"])

        company_df = company_df.drop_duplicates(subset=["transaction_id"], keep="first").set_index("transaction_id")
        processor_df = processor_df.drop_duplicates(subset=["transaction_id"], keep="first").set_index("transaction_id")

        all_ids = set(company_df.index).union(set(processor_df.index))

        results = []

        for txn_id in all_ids:

            company_row = company_df.loc[txn_id] if txn_id in company_df.index else None
            processor_row = processor_df.loc[txn_id] if txn_id in processor_df.index else None

            if txn_id in company_duplicates or txn_id in processor_duplicates:
                results.append({
                    "transaction_id": txn_id,
                    "status": ReconciliationStatus.DUPLICATE,
                    "company_amount": company_row["amount"] if company_row is not None else None,
                    "processor_amount": processor_row["amount"] if processor_row is not None else None,
                    "company_status": company_row["status"] if company_row is not None else None,
                    "processor_status": processor_row["status"] if processor_row is not None else None,
                })
                continue

            if company_row is None:
                results.append({
                    "transaction_id": txn_id,
                    "status": ReconciliationStatus.MISSING_IN_COMPANY,
                    "company_amount": None,
                    "processor_amount": processor_row["amount"],
                    "company_status": None,
                    "processor_status": processor_row["status"]
                })
                continue

            if processor_row is None:
                results.append({
                    "transaction_id": txn_id,
                    "status": ReconciliationStatus.MISSING_IN_PROCESSOR,
                    "company_amount": company_row["amount"],
                    "processor_amount": None,
                    "company_status": company_row["status"],
                    "processor_status": None
                })
                continue

            if company_row["amount"] != processor_row["amount"]:
                results.append({
                    "transaction_id": txn_id,
                    "status": ReconciliationStatus.AMOUNT_MISMATCH,
                    "company_amount": company_row["amount"],
                    "processor_amount": processor_row["amount"],
                    "company_status": company_row["status"],
                    "processor_status": processor_row["status"]
                })
                continue

            if company_row["status"] != processor_row["status"]:
                results.append({
                    "transaction_id": txn_id,
                    "status": ReconciliationStatus.STATUS_MISMATCH,
                    "company_amount": company_row["amount"],
                    "processor_amount": processor_row["amount"],
                    "company_status": company_row["status"],
                    "processor_status": processor_row["status"]
                })
                continue

            results.append({
                "transaction_id": txn_id,
                "status": ReconciliationStatus.MATCHED,
                "company_amount": company_row["amount"],
                "processor_amount": processor_row["amount"],
                "company_status": company_row["status"],
                "processor_status": processor_row["status"]
            })

        # Pandas row access produces NumPy scalars. psycopg2 can serialize their
        # repr (e.g. np.float64(...)) as SQL instead of a numeric literal.
        # Normalize every result branch before values cross the DB boundary.
        for result in results:
            for field in ("company_amount", "processor_amount"):
                value = result[field]
                result[field] = None if value is None else float(value)

        return results
