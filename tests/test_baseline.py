import io
import json
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from medika.analysis import decide
from medika.app import create_app
from medika.config import Settings
from medika.provider import BaselineProvider, ProviderError, parse_json
from medika.store import Store

TEXT = """DATA SINTETIS UNTUK PENGUJIAN
Klinik Contoh Medika
Surat Keterangan Sakit
Nama: Pasien Contoh
Pasien memerlukan istirahat selama 3 hari.
Mulai: 2026-11-20
Sampai: 2026-11-22
Dokter: dr. Contoh
Tanggal surat: 2026-11-20
"""


def result(**overrides):
    data = {"document_type": "sick_letter", "patient_name": "Pasien Contoh", "doctor_name": "dr. Contoh",
            "facility_name": "Klinik Contoh Medika", "issue_date": "2026-11-20", "rest_start": "2026-11-20",
            "rest_end": "2026-11-22", "rest_days": 3,
            "sick_statement": "Pasien memerlukan istirahat selama 3 hari.", "uncertainties": [],
            "summary": "Dokumen menyatakan kebutuhan istirahat."}
    data.update(overrides)
    return data


def png():
    data = io.BytesIO()
    Image.new("RGB", (600, 800), "white").save(data, format="PNG")
    return data.getvalue()


def test_pass_does_not_claim_authenticity():
    decision = decide(result(), TEXT)
    assert decision["status"] == "pass"
    assert decision["authenticity"] == "not_verified"
    assert decision["tampering"] == "not_assessed"


@pytest.mark.parametrize("kind", ["health_letter", "visit_letter", "blank_form", "receipt", "prescription"])
def test_non_sick_documents_fail_type_check(kind):
    assert decide(result(document_type=kind), TEXT)["status"] == "fail"


def test_unknown_document_is_not_called_fake():
    assert decide(result(document_type="unknown"), TEXT)["status"] == "needs_review"


def test_fabricated_patient_or_evidence_cannot_pass():
    assert decide(result(patient_name="Nama yang tidak ada"), TEXT)["status"] == "needs_review"
    assert decide(result(sick_statement="Isi yang tidak ada dalam teks"), TEXT)["status"] == "needs_review"


def test_joined_ocr_words_are_supported_without_fuzzy_name_guessing():
    joined = TEXT.replace("Klinik Contoh Medika", "KLINIKCONTOHMEDIKA")
    assert decide(result(), joined)["status"] == "pass"


def test_date_contradictions_are_checked_in_python():
    assert decide(result(rest_days=2), TEXT)["status"] == "fail"
    assert decide(result(rest_start="2026-11-23"), TEXT)["status"] == "fail"


def test_ambiguous_date_goes_to_review():
    assert decide(result(rest_end="22 Nov?"), TEXT)["status"] == "needs_review"


@pytest.mark.parametrize("bad", [True, "3", -1, 0])
def test_invalid_duration_is_not_silently_coerced(bad):
    with pytest.raises(ProviderError):
        decide(result(rest_days=bad), TEXT)


def test_model_json_is_strict_and_no_arbitrary_code_is_executed():
    assert parse_json('```json\n{"ok": true}\n```') == {"ok": True}
    with pytest.raises(ProviderError):
        parse_json("__import__('os').system('anything')")
    with pytest.raises(ProviderError):
        parse_json("[]")


def test_provider_has_no_url_key_or_secret_in_browser_metadata():
    provider = BaselineProvider(Settings(base_url="https://example.invalid/v1", api_key="private-test-key", model="qwen-38"))
    public = json.dumps(provider.public())
    assert "example.invalid" not in public and "private-test-key" not in public


class FakeProvider:
    model = "qwen-38"
    def public(self):
        return {"ready": True, "configured": True, "model": self.model, "provider": "Qwen", "prompt_version": "test"}
    def check(self):
        return self.public()
    def analyze(self, text):
        return result(), {"model_ms": 1, "input_tokens": 20, "output_tokens": 20}


class FakeReader:
    def read(self, data, document):
        return TEXT, "synthetic_test_reader"


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(runtime=tmp_path, model="qwen-38"), provider=FakeProvider(), reader=FakeReader())
    with TestClient(app) as client:
        yield client


HEADERS = {"X-Medika-Request": "dashboard"}


def upload_and_wait(client, filename="test.png"):
    response = client.post("/api/runs", files={"file": (filename, png(), "image/png")}, headers=HEADERS)
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    for _ in range(100):
        run = client.get("/api/runs/" + run_id).json()
        if run["state"] not in {"queued", "running"}:
            return run
        time.sleep(.01)
    pytest.fail("Test job did not finish")


def test_upload_review_export_and_delete(client):
    run = upload_and_wait(client, "../../contoh.png")
    assert run["filename"] == "contoh.png"
    assert run["state"] == "completed" and run["result"]["passed"] is True
    assert "storage_name" not in run
    assert client.get("/api/runs/" + run["id"] + "/file").status_code == 200
    response = client.put("/api/runs/" + run["id"] + "/review", json={"label": "needs_review", "note": "Catatan uji"}, headers=HEADERS)
    assert response.status_code == 200 and response.json()["label"] == "needs_review"
    export = client.get("/api/export").json()
    assert "ocr_text" not in export["runs"][0] and "storage_name" not in export["runs"][0]
    assert export["runs"][0]["model"] == "qwen-38"
    assert client.delete("/api/runs/" + run["id"], headers=HEADERS).status_code == 200
    assert client.get("/api/runs/" + run["id"]).status_code == 404
    assert client.get("/api/runs").json() == {"runs": []}


def test_forged_extension_does_not_pass_content_validation(client):
    response = client.post("/api/runs", files={"file": ("letter.png", b"this is not a picture", "image/png")}, headers=HEADERS)
    assert response.status_code == 422


def test_cross_site_and_unmarked_mutations_are_rejected(client):
    assert client.post("/api/provider/check").status_code == 403
    assert client.post("/api/provider/check", headers={**HEADERS, "Origin": "https://other.invalid"}).status_code == 403


def test_unreadable_document_is_not_sent_to_model(tmp_path):
    class EmptyReader:
        def read(self, data, document): return "", "rapidocr"
    class NeverCall(FakeProvider):
        def analyze(self, text): raise AssertionError("Model should not run on unreadable input")
    app = create_app(Settings(runtime=tmp_path), provider=NeverCall(), reader=EmptyReader())
    with TestClient(app) as c:
        run = upload_and_wait(c)
    assert run["result"]["status"] == "needs_review"
    assert run["metrics"]["model_called"] is False


def test_provider_failure_is_not_a_document_rejection(tmp_path):
    class Broken(FakeProvider):
        def analyze(self, text): raise ProviderError("Layanan model belum dapat dihubungi.")
    app = create_app(Settings(runtime=tmp_path), provider=Broken(), reader=FakeReader())
    with TestClient(app) as c:
        run = upload_and_wait(c)
    assert run["state"] == "failed" and run["result"] is None


def test_ui_and_assets_are_served_with_private_headers(client):
    response = client.get("/")
    assert response.status_code == 200 and "Medika" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/.env").status_code == 404
    assert client.get("/api/health").json()["provider"]["model"] == "qwen-38"


def test_atomic_store_survives_restart_and_marks_interrupted_jobs(tmp_path):
    store = Store(tmp_path)
    record = {"id": "MDK-ABCDEF", "filename": "contoh.png", "mime": "image/png", "size": 123,
              "pages": 1, "created_at": "2026-11-27T00:00:00+00:00", "state": "queued", "stage": "queued", "storage_name": "MDK-ABCDEF.png"}
    store.create(record)
    restarted = Store(tmp_path)
    assert restarted.get("MDK-ABCDEF")["state"] == "failed"
    assert "dimulai ulang" in restarted.get("MDK-ABCDEF")["error"]
    restarted.update("MDK-ABCDEF", state="completed", result=json.dumps({"status": "pass"}), label="pass")
    again = Store(tmp_path)
    assert again.get("MDK-ABCDEF")["label"] == "pass"
    assert again.get("MDK-ABCDEF")["result"]["status"] == "pass"
    assert not list((tmp_path / "records").glob(".pending-*"))
