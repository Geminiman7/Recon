from app.services.dataframe_service import DataFrameService

class HeaderService:
    @staticmethod
    def read_headers(path):
        return list(DataFrameService.load_file(path, headers_only=True).columns)
