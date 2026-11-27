#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
  exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/run.py"
fi
PACKAGE_DIR=$(python3 "$PROJECT_DIR/scripts/bootstrap_runtime.py")
export PYTHONPATH="$PACKAGE_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$PROJECT_DIR/run.py"
