"""Exercise OCR + actual configured model using only fictional generated fixtures."""
import json
import os
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("MEDIKA_QA_URL", "http://127.0.0.1:8096")
HEADERS = {"X-Medika-Request": "dashboard"}
with httpx.Client(base_url=BASE, timeout=30, trust_env=False, headers=HEADERS) as client:
    health = client.post("/api/provider/check").json()
    assert health["ready"], health.get("message")
    for fixture, expected in (("contoh-surat-sakit.png", "sick_letter"), ("contoh-bukti-pembayaran.pdf", "receipt")):
        path = ROOT / "samples" / fixture
        response = client.post("/api/runs", files={"file": (fixture, path.read_bytes())})
        response.raise_for_status()
        run_id = response.json()["id"]
        print(json.dumps({"fixture": fixture, "run_id": run_id, "state": "submitted"}), flush=True)
        for _ in range(240):
            run = client.get("/api/runs/" + run_id).json()
            if run["state"] not in {"running", "queued"}:
                break
            time.sleep(1)
        assert run["state"] == "completed", {"state": run["state"], "error": run.get("error")}
        predicted = run["result"].get("fields", {}).get("document_type")
        print(json.dumps({"fixture": fixture, "model": run["model"], "status": run["result"]["status"],
                          "document_type": predicted, "expected_type": expected, "metrics": run["metrics"],
                          "reasons": run["result"]["reasons"]}, ensure_ascii=False), flush=True)
        assert run["metrics"].get("model_called") is True
        assert predicted == expected
        manual = "pass" if expected == "sick_letter" else "fail"
        response = client.put("/api/runs/" + run_id + "/review", json={"label": manual, "note": "Fixture sintetis untuk smoke test; bukan evaluasi akurasi."})
        response.raise_for_status()
    export = client.get("/api/export").json()
    assert len(export["runs"]) == 2
    print(json.dumps({"live_smoke": "passed", "model": health["model"], "review_export": "passed"}), flush=True)
