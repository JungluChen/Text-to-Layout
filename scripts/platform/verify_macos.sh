#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf '%s\n' 'ERROR: macOS certification requires a real macOS host.' >&2
  exit 2
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  printf '%s\n' 'ERROR: this collector certifies Apple Silicon only; Intel remains untested.' >&2
  exit 2
fi

python3 scripts/platform/verify_platform.py \
  --platform macos \
  --python-version 3.11 \
  --python-version 3.12 \
  --output out/platform/macos_arm64.json \
  --markdown-out docs/platforms/macos_arm64.md \
  "$@"

