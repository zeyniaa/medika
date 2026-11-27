from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


@dataclass
class Settings:
    runtime: Path = field(default_factory=lambda: ROOT / "runtime")
    source_env: Path = field(default_factory=lambda: Path("/home/jds2/Simpul/.env"))
    base_url: str = field(default="", repr=False)
    api_key: str = field(default="", repr=False)
    model: str = ""
    dns_absolute: bool = False
    timeout: float = 150
    max_file_bytes: int = 10 * 1024 * 1024
    max_pages: int = 3
    max_pixels: int = 30_000_000
    port: int = 8096
    host: str = "127.0.0.1"
    require_token: str = field(default="", repr=False)

    @classmethod
    def load(cls) -> "Settings":
        local = read_env(ROOT / ".env")
        def get(name: str, default: str = "") -> str:
            return os.environ.get(name, local.get(name, default))
        source = Path(get("MEDIKA_SIMPUL_ENV", "/home/jds2/Simpul/.env"))
        shared = read_env(source)
        return cls(
            runtime=Path(get("MEDIKA_RUNTIME_DIR", str(ROOT / "runtime"))),
            source_env=source,
            base_url=get("MEDIKA_MODEL_URL", shared.get("MODEL_URL", "")).rstrip("/"),
            api_key=get("MEDIKA_MODEL_API_KEY", shared.get("MODEL_API_KEY", "")),
            model=get("MEDIKA_MODEL_NAME", "qwen-38"),
            dns_absolute=get("MEDIKA_DNS_ABSOLUTE", shared.get("MODEL_DNS_ABSOLUTE", "false")).lower() in {"1", "true", "yes"},
            port=int(get("MEDIKA_PORT", "8096")),
            host=get("MEDIKA_HOST", "127.0.0.1"),
            require_token=get("MEDIKA_ACCESS_TOKEN"),
        )

    def validate_provider(self) -> bool:
        url = urlsplit(self.base_url)
        return bool(url.scheme in {"http", "https"} and url.hostname and self.api_key and not url.username and not url.password and not url.query and not url.fragment)

    def prepare(self) -> None:
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.runtime / "uploads").mkdir(mode=0o700, exist_ok=True)

