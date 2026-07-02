#!/bin/sh
# One-command simulator bootstrap (POSIX wrapper).
# Usage: ./scripts/install_simulators.sh [--detect-only] [--strict]
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python
exec "$PYTHON" "$SCRIPT_DIR/bootstrap_simulators.py" "$@"
