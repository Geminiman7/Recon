import pandas as pd
from app.core.config import settings
from app.services.storage_service import materialize
from app.services.file_validation import validate_file


class DataFrameService:
    @staticmethod
    def load_file(reference: str, headers_only=False):
        with materialize(reference) as path:
            validate_file(path)
            options = {"nrows": 0 if headers_only else settings.MAX_SPREADSHEET_ROWS + 1}
            frame = pd.read_csv(path, **options) if path.suffix.lower() == ".csv" else pd.read_excel(path, **options)
            if len(frame) > settings.MAX_SPREADSHEET_ROWS or len(frame.columns) > settings.MAX_SPREADSHEET_COLUMNS:
                raise ValueError("Spreadsheet dimensions exceed the limit.")
            return frame
