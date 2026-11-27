from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

from .analysis import POLICY_VERSION, decide
from .config import ROOT, Settings
from .documents import DocumentError, DocumentReader, inspect_document
from .provider import BaselineProvider, ProviderError
from .store import Store, now


class Review(BaseModel):
    label: Literal["pass", "fail", "needs_review"] | None
    note: str = Field(default="", max_length=1000)


def create_app(settings: Settings | None = None, provider=None, reader=None):
    settings = settings or Settings.load()
    settings.prepare()
    store = Store(settings.runtime)
    provider = provider or BaselineProvider(settings)
    reader = reader or DocumentReader()
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="medika-baseline")
    pending = threading.BoundedSemaphore(8)
    check_lock = threading.Lock()
    app = FastAPI(title="Medika", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.provider, app.state.settings = store, provider, settings

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        # Loopback by default. For an explicitly exposed server, the token lives only
        # in the server environment and is required on every page and API request.
        host = request.headers.get("host", "").split(":", 1)[0].lower()
        if not settings.require_token and host not in {"localhost", "127.0.0.1", "testserver"}:
            return JSONResponse({"detail": "Medika hanya dapat diakses melalui koneksi lokal."}, status_code=403)
        if settings.require_token:
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not hmac.compare_digest(supplied, settings.require_token):
                return Response("Akses Medika memerlukan autentikasi server.", status_code=401, headers={"WWW-Authenticate": "Bearer"})
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Permintaan lintas situs ditolak."}, status_code=403)
            if request.headers.get("x-medika-request") != "dashboard":
                return JSONResponse({"detail": "Header permintaan Medika diperlukan."}, status_code=403)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Ukuran permintaan tidak valid."}, status_code=400)
            if length > settings.max_file_bytes + 128 * 1024:
                return JSONResponse({"detail": "Berkas maksimal 10 MB."}, status_code=413)
        response = await call_next(request)
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; frame-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
        })
        return response

    @app.get("/")
    def home():
        return FileResponse(ROOT / "static/index.html")

    @app.get("/api/health")
    def health():
        return {"name": "Medika", "provider": provider.public(), "policy_version": POLICY_VERSION,
                "max_file_mb": 10, "max_pages": settings.max_pages, "storage": "server_private", "authenticity": "not_verified"}

    @app.post("/api/provider/check")
    def provider_check():
        if not check_lock.acquire(blocking=False):
            raise HTTPException(409, "Pemeriksaan koneksi sedang berjalan.")
        try:
            return provider.check()
        finally:
            check_lock.release()

    @app.get("/api/runs")
    def runs():
        return {"runs": store.list()}

    def execute(run_id: str, path: Path, document):
        started = time.monotonic()
        try:
            store.update(run_id, state="running", stage="reading")
            text, method = reader.read(path.read_bytes(), document)
            if len(text.strip()) < 25:
                result = {"status": "needs_review", "passed": False, "fields": {}, "checks": [],
                          "reasons": ["Teks belum cukup terbaca. Coba foto yang lebih jelas."],
                          "authenticity": "not_verified", "tampering": "not_assessed", "policy_version": POLICY_VERSION}
                store.update(run_id, state="completed", stage="completed", result=json.dumps(result), reader=method,
                             ocr_text=text, metrics=json.dumps({"total_ms": round((time.monotonic()-started)*1000), "model_called": False}))
                return
            store.update(run_id, stage="analyzing", reader=method, ocr_text=text)
            raw, metrics = provider.analyze(text)
            store.update(run_id, stage="checking", model=provider.model)
            result = decide(raw, text)
            metrics.update({"total_ms": round((time.monotonic() - started) * 1000), "model_called": True})
            store.update(run_id, state="completed", stage="completed", result=json.dumps(result, ensure_ascii=False), metrics=json.dumps(metrics))
        except (ProviderError, DocumentError) as exc:
            store.update(run_id, state="failed", stage="failed", error=str(exc), model=provider.model or None)
        except Exception:
            # Never return raw upstream bodies, URLs, credentials, OCR text or tracebacks.
            store.update(run_id, state="failed", stage="failed", error="Proses pembacaan belum berhasil. Berkas atau layanan belum dapat diproses; ini bukan keputusan tentang surat.")
        finally:
            pending.release()

    @app.post("/api/runs", status_code=202)
    async def upload(file: UploadFile = File(...)):
        data = await file.read(settings.max_file_bytes + 1)
        await file.close()
        try:
            document = inspect_document(data, settings)
        except DocumentError as exc:
            raise HTTPException(422, str(exc)) from None
        if not pending.acquire(blocking=False):
            raise HTTPException(429, "Antrean baseline penuh. Tunggu satu pengujian selesai.")
        run_id = "MDK-" + secrets.token_hex(6).upper()
        name = Path((file.filename or "dokumen").replace("\\", "/")).name
        name = "".join(char for char in name if ord(char) >= 32)[:160] or "dokumen"
        storage_name = run_id + document.extension
        path = settings.runtime / "uploads" / storage_name
        try:
            path.write_bytes(data)
            path.chmod(0o600)
            store.create({"id": run_id, "filename": name, "mime": document.mime, "size": len(data),
                          "pages": document.pages, "created_at": now(), "state": "queued", "stage": "queued", "storage_name": storage_name})
            pool.submit(execute, run_id, path, document)
        except Exception:
            pending.release()
            path.unlink(missing_ok=True)
            raise
        return {"id": run_id}

    def get_run(run_id: str, private=False):
        record = store.get(run_id, private=private)
        if not record:
            raise HTTPException(404, "Pengujian tidak ditemukan.")
        return record

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str):
        return get_run(run_id)

    @app.get("/api/runs/{run_id}/file")
    def run_file(run_id: str):
        run = get_run(run_id, private=True)
        return FileResponse(settings.runtime / "uploads" / run["storage_name"], media_type=run["mime"], filename=run["filename"], content_disposition_type="inline")

    @app.put("/api/runs/{run_id}/review")
    def review(run_id: str, body: Review):
        run = get_run(run_id)
        if run["state"] != "completed":
            raise HTTPException(409, "Label penilai hanya dapat dicatat setelah pengujian selesai.")
        store.update(run_id, label=body.label, note=body.note.strip())
        return get_run(run_id)

    @app.delete("/api/runs/{run_id}")
    def delete(run_id: str):
        run = get_run(run_id, private=True)
        if run["state"] in {"queued", "running"}:
            raise HTTPException(409, "Tunggu pengujian selesai sebelum menghapusnya.")
        (settings.runtime / "uploads" / run["storage_name"]).unlink(missing_ok=True)
        store.delete(run_id)
        return {"deleted": True}

    @app.get("/api/export")
    def export():
        # Explicit download; no raw uploads or OCR bodies are included.
        payload = {"project": "Medika", "exported_at": now(), "policy_version": POLICY_VERSION,
                   "authenticity": "not_verified", "runs": store.list()}
        return Response(json.dumps(payload, ensure_ascii=False, indent=2), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="medika-baseline.json"'})

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app

