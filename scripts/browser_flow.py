"""Verify automatic processing after selecting a synthetic file, then delete it."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

root = Path(__file__).resolve().parents[1]
base = os.environ.get("MEDIKA_QA_URL", "http://127.0.0.1:8096")
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base, wait_until="networkidle")
    page.get_by_text("Siap digunakan", exact=True).wait_for(timeout=30000)
    initial = len(page.request.get(base + "/api/runs").json()["runs"])
    run_id = None
    try:
        with page.expect_response(lambda r: r.request.method == "POST" and r.url == base + "/api/runs") as upload:
            page.locator("#file-input").set_input_files(str(root / "samples/contoh-bukti-pembayaran.png"))
        assert upload.value.status == 202
        run_id = upload.value.json()["id"]
        assert page.locator("#file-preview").is_visible()
        expect(page.locator("#result-badge")).to_have_text("Tidak lolos", timeout=180000)
        assert page.locator("#result-content").get_by_text("Kuitansi", exact=True).is_visible()
        record = page.request.get(base + "/api/runs/" + run_id).json()
        assert record["model"] == "qwen-38" and record["metrics"]["model_called"]
        assert record["result"]["authenticity"] == "not_verified"
        page.get_by_text("Lihat rincian", exact=True).click()
        page.get_by_text("Teks yang terbaca", exact=True).click()
        assert page.locator("#result-content pre").is_visible()
        for width in [1440, 768, 390]:
            page.set_viewport_size({"width": width, "height": 1000})
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Hapus hasil", exact=True).click()
        expect(page.locator("#result-empty")).to_be_visible()
        assert len(page.request.get(base + "/api/runs").json()["runs"]) == initial
        run_id = None
        assert not errors, errors
    finally:
        if run_id:
            record = page.request.get(base + "/api/runs/" + run_id).json()
            if record.get("state") in {"completed", "failed"}:
                page.request.delete(base + "/api/runs/" + run_id, headers={"X-Medika-Request": "dashboard", "Origin": base})
        browser.close()
print(json.dumps({"automatic_upload": "passed", "actual_model_result": "passed", "details": "passed", "responsive_result": "passed", "confirmed_delete": "passed", "console_errors": errors}))
