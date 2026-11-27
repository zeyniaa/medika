"""Restore the pinned private runtime onto local disk, including after /tmp cleanup."""
import fcntl
import hashlib
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
archive = root / ".runtime/dependencies.tar.gz"
manifest = root / ".runtime/manifest.json"
if not archive.is_file():
    packages = root / ".packages"
    if (packages / "fastapi").is_dir():
        print(packages)
        raise SystemExit(0)
    raise SystemExit("Install requirements.txt into a .venv before starting Medika.")
metadata = json.loads(manifest.read_text())
if list(sys.version_info[:2]) != metadata["python"]:
    raise SystemExit("The bundled runtime requires Python 3.10. Use a .venv for another version.")
cache = Path(tempfile.gettempdir()) / ("medika-packages-" + str(os.getuid()) + "-" + metadata["sha256"][:16])
cache.mkdir(mode=0o700, exist_ok=True)
if cache.is_symlink() or cache.stat().st_uid != os.getuid():
    raise SystemExit("Runtime cache ownership is invalid.")
with (cache / ".lock").open("w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    if not (cache / ".ready").is_file():
        digest = hashlib.sha256()
        with archive.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != metadata["sha256"]:
            raise SystemExit("The packaged runtime checksum does not match.")
        with tarfile.open(archive, "r:gz") as bundle:
            members = bundle.getmembers()
            for member in members:
                resolved = (cache / member.name).resolve()
                if not resolved.is_relative_to(cache.resolve()) or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise SystemExit("Unexpected entry in runtime archive.")
            bundle.extractall(cache, members=members)
        (cache / ".ready").write_text(metadata["sha256"])
print(cache)
