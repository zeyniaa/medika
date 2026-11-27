"""Activate the agreed JDS installation; stop only this task's owned preview."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path
import urllib.request

root = Path("/home/jds2/Medika")
if not (root / ".runtime/dependencies.tar.gz").is_file():
    raise SystemExit("Medika dependencies have not finished installing.")
preview_pid = Path("/tmp/medika-preview-runtime/server.pid")
if preview_pid.is_file():
    try:
        pid = int(preview_pid.read_text())
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
        if b"/tmp/medika-source/run.py" in command:
            os.kill(pid, signal.SIGTERM)
            for _ in range(30):
                if not Path(f"/proc/{pid}").exists():
                    break
                time.sleep(.1)
    except (ValueError, OSError):
        pass
subprocess.run(["python3", str(root / "scripts/start_service.py")], cwd=root, check=True)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(50):
    try:
        with opener.open("http://127.0.0.1:8096/api/health", timeout=2) as response:
            body = json.load(response)
        if body.get("name") == "Medika":
            request = urllib.request.Request("http://127.0.0.1:8096/api/provider/check", method="POST", headers={"X-Medika-Request": "dashboard"})
            with opener.open(request, timeout=30) as response:
                provider = json.load(response)
            print(json.dumps({"installed": str(root), "http": 200, "model": provider.get("model"), "connected": provider.get("ready")}, ensure_ascii=False))
            break
    except Exception:
        time.sleep(.2)
else:
    raise SystemExit("Medika did not become ready; inspect its private server log.")
