import unittest

import pandas as pd

from app.models.reconciliation_result import ReconciliationStatus
from app.services.reconciliation_engine import ReconciliationEngine


class ReconciliationEngineTests(unittest.TestCase):
    def test_all_result_amounts_are_native_numbers_for_postgres(self):
        from psycopg2.extensions import adapt
        for dtype in ("float64", "int64"):
            with self.subTest(dtype=dtype):
                company = pd.DataFrame([
                    ["matched", 5000, "SUCCESS"],
                    ["amount", 10, "SUCCESS"],
                    ["status", 20, "FAILED"],
                    ["company-only", 30, "SUCCESS"],
                    ["duplicate", 40, "SUCCESS"],
                    ["duplicate", 40, "SUCCESS"],
                ], columns=["transaction_id", "amount", "status"])
                processor = pd.DataFrame([
                    ["matched", 5000, "SUCCESS"],
                    ["amount", 11, "SUCCESS"],
                    ["status", 20, "SUCCESS"],
                    ["processor-only", 50, "SUCCESS"],
                    ["duplicate", 40, "SUCCESS"],
                ], columns=["transaction_id", "amount", "status"])
                company["amount"] = company["amount"].astype(dtype)
                processor["amount"] = processor["amount"].astype(dtype)
                results = ReconciliationEngine.reconcile(company, processor)
                self.assertEqual({row["status"] for row in results}, set(ReconciliationStatus))
                for row in results:
                    for field in ("company_amount", "processor_amount"):
                        value = row[field]
                        if value is not None:
                            self.assertIs(type(value), float)
                            self.assertEqual(float(adapt(value).getquoted()), value)
                by_id = {row["transaction_id"]: row for row in results}
                self.assertEqual(by_id["matched"]["company_amount"], 5000.0)
                self.assertIsNone(by_id["company-only"]["processor_amount"])
                self.assertIsNone(by_id["processor-only"]["company_amount"])

    def test_transaction_in_later_processor_file_is_not_missing(self):
        company = pd.DataFrame([
            {"transaction_id": "company-only", "amount": 100, "status": "SUCCESS"},
            {"transaction_id": "in-second-file", "amount": 200, "status": "SUCCESS"},
        ])
        first_processor = pd.DataFrame([
            {"transaction_id": "company-only", "amount": 100, "status": "SUCCESS"},
        ])
        second_processor = pd.DataFrame([
            {"transaction_id": "in-second-file", "amount": 200, "status": "SUCCESS"},
        ])

        results = ReconciliationEngine.reconcile(
            company, pd.concat([first_processor, second_processor], ignore_index=True)
        )
        statuses = {row["transaction_id"]: row["status"] for row in results}

        self.assertEqual(statuses["company-only"], ReconciliationStatus.MATCHED)
        self.assertEqual(statuses["in-second-file"], ReconciliationStatus.MATCHED)
        self.assertNotIn(ReconciliationStatus.MISSING_IN_PROCESSOR, statuses.values())

    def test_missing_in_processor_requires_absence_from_combined_dataset(self):
        company = pd.DataFrame([
            {"transaction_id": "not-in-any-file", "amount": 100, "status": "SUCCESS"},
        ])
        processors = pd.DataFrame([
            {"transaction_id": "other-transaction", "amount": 100, "status": "SUCCESS"},
        ])

        results = ReconciliationEngine.reconcile(company, processors)
        statuses = {row["transaction_id"]: row["status"] for row in results}

        self.assertEqual(
            statuses["not-in-any-file"], ReconciliationStatus.MISSING_IN_PROCESSOR
        )


if __name__ == "__main__":
    unittest.main()
