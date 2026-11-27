from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, runtime: Path):
        self.runtime = runtime
        self.path = runtime / "records"
        self.path.mkdir(mode=0o700, exist_ok=True)
        self._lock = threading.RLock()
        self._records = {}
        for file in self.path.glob("MDK-*.json"):
            record = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("id") != file.stem:
                raise ValueError("Stored Medika record is invalid")
            self._records[record["id"]] = record
            if record["state"] in {"queued", "running"}:
                record.update(state="failed", stage="failed", error="Proses terhenti saat server dimulai ulang. Jalankan pengujian baru bila diperlukan.")
                self._save(record)

    def _save(self, record):
        target = self.path / (record["id"] + ".json")
        temporary = self.path / (".pending-" + secrets.token_hex(8))
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def create(self, record: dict):
        with self._lock:
            full = {"result": None, "error": None, "model": None, "metrics": None,
                    "ocr_text": None, "label": None, "note": "", "reader": None, **record}
            self._save(full)
            self._records[full["id"]] = full

    def update(self, run_id: str, **values):
        allowed = {"state", "stage", "result", "error", "model", "metrics", "ocr_text", "label", "note", "reader"}
        if not values or not values.keys() <= allowed:
            raise ValueError("Unknown stored fields")
        with self._lock:
            record = {**self._records[run_id], **values}
            self._save(record)
            self._records[run_id] = record

    def get(self, run_id: str, *, private=False):
        with self._lock:
            row = self._records.get(run_id)
        if row is None:
            return None
        data = dict(row)
        for key in ("result", "metrics"):
            data[key] = json.loads(data[key]) if data[key] else None
        if not private:
            data.pop("storage_name", None)
        return data

    def list(self):
        with self._lock:
            rows = sorted((dict(record) for record in self._records.values()), key=lambda record: record["created_at"], reverse=True)
        result = []
        for row in rows:
            data = dict(row)
            for key in ("result", "metrics"):
                data[key] = json.loads(data[key]) if data[key] else None
            data.pop("storage_name", None)
            data.pop("ocr_text", None)
            result.append(data)
        return result

    def delete(self, run_id):
        with self._lock:
            (self.path / (run_id + ".json")).unlink(missing_ok=True)
            self._records.pop(run_id, None)

