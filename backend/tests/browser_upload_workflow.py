"""Optional Edge smoke test: run with Playwright installed, from backend.

Uses real page scripts and FastAPI handlers with an isolated SQLite database
and temporary storage. No requests are sent to a deployed service.
"""
import mimetypes
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import test_production_boundaries as fixtures
from playwright.sync_api import sync_playwright, expect
from app.models.processor import Processor
from app.services.reconciliation_service import ReconciliationService


def main():
    fixture = fixtures.BoundaryTests()
    fixture.setUpClass()
    fixture.setUp()
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    errors = []
    queued = []
    try:
        processor = Processor(name="Browser processor", is_active=True)
        fixture.db.add(processor)
        fixture.db.commit()
        response = fixture.client.post("/jobs", json={"job_name": "Browser workflow"}, headers=fixture.csrf())
        assert response.status_code == 200, response.text
        job_id = response.json()["id"]

        def publish(task, *args):
            queued.append(args)
            return True

        def serve(route):
            request = route.request
            url = urlsplit(request.url)
            if url.path.startswith("/api/"):
                path = url.path[4:] + ("?" + url.query if url.query else "")
                # Drive the queued attempt on a status poll, through the real service.
                if path == f"/jobs/{job_id}" and queued:
                    args = queued.pop(0)
                    from uuid import UUID
                    with fixture.Session() as db:
                        ReconciliationService.run(db, UUID(args[0]), UUID(args[1]), UUID(args[2]), args[3])
                headers = {key: value for key, value in request.all_headers().items()
                           if key not in {"host", "content-length", "cookie"}}
                result = fixture.client.request(request.method, path, content=request.post_data_buffer, headers=headers)
                route.fulfill(status=result.status_code, body=result.content,
                    headers={key: value for key, value in result.headers.items()
                             if key not in {"content-length", "content-encoding"}})
                return
            path = frontend / url.path.lstrip("/")
            if not path.suffix:
                path = path.with_suffix(".html")
            if path.is_file() and path.resolve().is_relative_to(frontend):
                route.fulfill(path=str(path), content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")
            else:
                route.fulfill(status=404, body="Not found")

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(fixtures.storage, "ROOT", Path(folder)), \
                patch.object(fixtures.settings, "STORAGE_BACKEND", "local"), \
                patch.object(fixtures.settings, "FRONTEND_URL", "http://testserver"), \
                patch.object(fixtures.settings, "RECONCILIATION_MODE", "async"), \
                patch("app.core.redis_health.publish", side_effect=publish), sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            try:
                context = browser.new_context()
                context.route("**/*", serve)
                context.add_cookies([{"name": cookie.name, "value": cookie.value, "url": "http://testserver"}
                                     for cookie in fixture.client.cookies.jar])
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("dialog", lambda dialog: (errors.append(dialog.message), dialog.accept()))
                page.goto("http://testserver/uploads")
                page.locator("#jobSelect").select_option(job_id)
                for kind, content in (
                    ("company", b"transaction_id,amount,status\nmatch,100,SUCCESS\nmissing,20,SUCCESS\n"),
                    ("processor", b"transaction_id,amount,status\nmatch,100,SUCCESS\n"),
                ):
                    page.locator("label").filter(has=page.locator(f'input[name="file_type"][value="{kind}"]')).click()
                    if kind == "processor":
                        page.locator("#processorSelect").select_option(str(processor.id))
                    page.locator("#fileInput").set_input_files({"name": f"{kind}.csv", "mimeType": "text/csv", "buffer": content})
                    with page.expect_response(lambda response: response.url.endswith(f"/api/uploads/{kind}") and response.request.method == "POST") as uploaded:
                        page.locator("#uploadBtn").click()
                    assert uploaded.value.status == 200, uploaded.value.text()
                    expect(page.locator("#uploadBtn")).to_be_enabled()
                expect(page.locator("#totalUploads")).to_have_text("2")
                uploads = fixture.client.get(f"/uploads/job/{job_id}").json()
                ids = {row["upload_type"]: row["id"] for row in uploads}
                page.goto("http://testserver/mapping")
                page.locator("#jobSelect").select_option(job_id)
                page.locator("#companyFile").select_option(ids["COMPANY"])
                page.locator("#processorFile").select_option(ids["PROCESSOR"])
                page.locator("#detectColumnsBtn").click()
                for side in ("company", "processor"):
                    for field in ("transaction_id", "amount", "status"):
                        page.locator(f"#{side}_{field}").select_option(field)
                page.locator("#saveMappingBtn").click()
                expect(page.locator("#mappingStatus")).to_have_text("Mapping complete")
                page.goto("http://testserver/reconciliation")
                page.locator("#jobSelect").select_option(job_id)
                page.locator("#runBtn").click()
                expect(page.locator("#resultPanel")).to_be_visible()
                expect(page.locator("#totalCount")).to_have_text("2")
                expect(page.locator("#matchedCount")).to_have_text("1")
                expect(page.locator("#missingCount")).to_have_text("1")
                page.locator('[onclick="viewResults()"]').click()
                expect(page.locator("#resultsSection")).to_be_visible()
                expect(page.locator("#totalCount")).to_have_text("2")
                page.locator("#statusFilter").select_option("MATCHED")
                expect(page.locator("#resultsTable tbody tr")).to_have_count(1)
                expect(page.locator("#resultsTable tbody")).to_contain_text("match")
                assert not errors, errors
                print("PASS: browser uploads -> mapping -> queued reconciliation -> results -> filtering")
            finally:
                browser.close()
    finally:
        fixture.tearDown()
        fixture.doCleanups()


if __name__ == "__main__":
    main()
