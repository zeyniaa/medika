"""Start Medika locally; server credentials never reach the browser."""
import os
import uvicorn
from medika.app import create_app
from medika.config import Settings

if __name__ == "__main__":
    settings = Settings.load()
    host = settings.host
    if host not in {"127.0.0.1", "localhost"} and not settings.require_token:
        raise SystemExit("MEDIKA_ACCESS_TOKEN diperlukan sebelum membuka akses jaringan.")
    uvicorn.run(create_app(settings), host=host, port=settings.port, access_log=False)
