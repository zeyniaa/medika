"""Bundle the already-tested dependencies; do not include browsers or credentials."""
import hashlib
import json
import tarfile
from pathlib import Path

source = Path("/tmp/medika-python-runtime")
archive = Path("/tmp/medika-dependencies.tar.gz")
def selected(info):
    name = info.name.split("/", 1)[0]
    if name.startswith(("playwright", "greenlet", "pypdf-")) or name == "pypdf" or "__pycache__" in info.name or name == "bin":
        return None
    return info
with tarfile.open(archive, "w:gz", compresslevel=1) as bundle:
    for item in source.iterdir():
        bundle.add(item, arcname=item.name, filter=selected)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
Path("/tmp/medika-runtime-manifest.json").write_text(json.dumps({"python": [3, 10], "sha256": digest}))
print(json.dumps({"archive_mb": round(archive.stat().st_size/1024/1024,1), "sha256": digest}))
