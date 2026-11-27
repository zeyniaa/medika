"""Check the focused upload/results UI on the configured Medika server."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

base = os.environ.get("MEDIKA_QA_URL", "http://127.0.0.1:8096")
out = Path(os.environ.get("MEDIKA_QA_OUTPUT", "/tmp/medika-qa"))
out.mkdir(parents=True, exist_ok=True)
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = page.goto(base, wait_until="networkidle")
    assert response.status == 200
    assert response.headers.get("www-authenticate") is None
    page.get_by_text("Siap digunakan", exact=True).wait_for(timeout=30000)
    assert page.get_by_role("button", name="Tambah file", exact=False).is_visible()
    assert page.locator("#result-empty").is_visible()
    assert page.locator("#file-preview").is_hidden()
    assert page.get_by_role("navigation").count() == 0
    for width, height, name in [(1440, 1000, "desktop"), (768, 1024, "tablet"), (390, 844, "mobile")]:
        page.set_viewport_size({"width": width, "height": height})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        page.screenshot(path=str(out / ("dashboard-" + name + ".png")), full_page=True)
    page.locator("#file-input").set_input_files({"name": "wrong.txt", "mimeType": "text/plain", "buffer": b"synthetic test"})
    page.get_by_role("alert").get_by_text("Gunakan JPG, PNG, atau PDF.").wait_for()
    assert page.locator("#result-empty").is_visible()
    assert not errors, errors
    browser.close()
print(json.dumps({"desktop": "passed", "tablet": "passed", "mobile": "passed", "file_validation": "passed", "console_errors": errors, "screenshots": str(out)}))
