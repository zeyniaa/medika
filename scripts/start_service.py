"""Start a detached local Medika process, without changing Simpul services."""
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runtime = Path(os.environ.get("MEDIKA_RUNTIME_DIR", str(root / "runtime")))
runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
pidfile = runtime / "server.pid"
if pidfile.exists():
    try:
        pid = int(pidfile.read_text())
        os.kill(pid, 0)
    except (ValueError, OSError):
        pass
    else:
        print("Medika process is already running.")
        raise SystemExit(0)
with (runtime / "server.log").open("ab") as log:
    process = subprocess.Popen([str(root / "scripts/start.sh")], cwd=root, stdin=subprocess.DEVNULL,
                               stdout=log, stderr=log, start_new_session=True)
pidfile.write_text(str(process.pid))
pidfile.chmod(0o600)
(runtime / "server.log").chmod(0o600)
print("Medika started; process ID:", process.pid)
