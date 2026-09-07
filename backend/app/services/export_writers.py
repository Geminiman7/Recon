from pathlib import Path
from itertools import islice
from openpyxl import Workbook
from app.core.config import settings

COLUMNS = ["transaction_id", "company_amount", "processor_amount", "difference", "company_status", "processor_status", "status"]
MIME = {"excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}
EXTENSION = {"excel": "xlsx", "pdf": "pdf"}


def safe_cell(value):
    if isinstance(value, str):
        if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
            value = "'" + value
        return "".join(c for c in value if ord(c) >= 32 or c in "\t\n\r")[:32767]
    return value


def write_excel(rows, path):
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Results")
    sheet.append(COLUMNS)
    size = count = 0
    try:
        for row in rows:
            values = [safe_cell(row[key]) for key in COLUMNS]
            size += sum(len(str(v).encode("utf-8")) * 6 for v in values) + 1024
            if size > settings.EXPORT_MAX_BYTES:
                raise ValueError("Export exceeds the size limit. Narrow the filters.")
            sheet.append(values)
            count += 1
        book.save(path)
    finally:
        if not sheet.closed:
            sheet.close()
        writer = getattr(sheet, "_writer", None)
        if writer and Path(writer.out).exists():
            writer.cleanup()
        book.close()
    return count


def write_pdf(rows, path):
    # Buffer one page at a time; stream PDF objects directly to disk.
    offsets = {}
    page_ids = []
    count = 0
    with open(path, "wb") as output:
        output.write(b"%PDF-1.4\n")
        def obj(number, content):
            offsets[number] = output.tell()
            output.write(f"{number} 0 obj\n".encode() + content + b"\nendobj\n")
            if output.tell() > settings.EXPORT_MAX_BYTES:
                raise ValueError("Export exceeds the size limit. Narrow the filters.")
        obj(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        iterator = iter(rows)
        while True:
            batch = list(islice(iterator, 42))
            if not batch and page_ids:
                break
            page_id = 4 + len(page_ids) * 2
            page_ids.append(page_id)
            commands = ["BT /F1 8 Tf 30 560 Td 12 TL", "(Recon Reconciliation Results) Tj T*"]
            for row in batch:
                line = " | ".join(str(row[key]) if row[key] is not None else "-" for key in COLUMNS)[:160]
                line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\r", " ").replace("\n", " ")
                commands.append(f"({line}) Tj T*")
                count += 1
            if not batch:
                commands.append("(No results match the filters.) Tj T*")
            commands.append("ET")
            data = "\n".join(commands).encode("latin-1", "replace")
            obj(page_id, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode())
            obj(page_id + 1, f"<< /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream")
            if not batch:
                break
        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        kids = " ".join(f"{number} 0 R" for number in page_ids)
        obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
        xref = output.tell()
        length = max(offsets) + 1
        output.write(f"xref\n0 {length}\n0000000000 65535 f \n".encode())
        for number in range(1, length):
            output.write(f"{offsets[number]:010d} 00000 n \n".encode())
        output.write(f"trailer\n<< /Size {length} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return count
