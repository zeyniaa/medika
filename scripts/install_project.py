"""Install the prepared Medika checkout and isolated dependencies at its agreed path.

This script writes outside Simpul and therefore requires host filesystem approval.
It never copies source configuration files or user uploads.
"""
import os
import shutil
from pathlib import Path

os.umask(0o077)
source = Path(__file__).resolve().parents[1]
destination = Path("/home/jds2/Medika")
archive = Path("/tmp/medika-dependencies.tar.gz")
if not archive.is_file():
    raise SystemExit("Prepared isolated dependencies were not found.")
if destination.exists() and any(destination.iterdir()) and not (destination / "medika/config.py").is_file():
    raise SystemExit("Destination contains unrelated files; refusing to overwrite.")
shutil.copytree(source, destination, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("runtime", "__pycache__", ".pytest_cache", ".env", ".packages", ".runtime", "artifacts"))
(destination / ".runtime").mkdir(mode=0o700, exist_ok=True)
target_archive = destination / ".runtime/dependencies.tar.gz"
target_manifest = destination / ".runtime/manifest.json"
source_manifest = Path("/tmp/medika-runtime-manifest.json")
if not (target_archive.is_file() and target_manifest.is_file() and target_manifest.read_bytes() == source_manifest.read_bytes()
        and target_archive.stat().st_size == archive.stat().st_size):
    shutil.copyfile(archive, target_archive)
    shutil.copyfile(source_manifest, target_manifest)
# Remove only this installer's incomplete dependency copy; never touch user runtime.
partial = destination / ".packages"
if partial.is_dir() and not partial.is_symlink():
    shutil.rmtree(partial)
(destination / "scripts/start.sh").chmod(0o700)
(destination / "runtime").mkdir(mode=0o700, exist_ok=True)
print("Medika installed at", destination)
print("Server-side credentials remain in their original configuration; none were copied.")
