#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

IS_WSL=0
if [[ -n "${WSL_INTEROP:-}" ]] || grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL=1
fi

if ((IS_WSL == 0)); then
  python3 scripts/platform/verify_platform.py \
    --platform wsl2 \
    --output out/platform/wsl2_ubuntu.json \
    --markdown-out docs/platforms/wsl2_ubuntu.md \
    --blocked-reason "WSL2 clean-room execution is blocked: this report was generated on $(uname -s) $(uname -m), not inside WSL. Run 'bash scripts/platform/verify_wsl.sh' from Ubuntu on WSL2."
  exit 2
fi

printf '%s\n' 'WSL host evidence:'
uname -a
cat /proc/version
lsb_release -a

python3 scripts/platform/verify_platform.py \
  --platform wsl2 \
  --python-version 3.11 \
  --output out/platform/wsl2_ubuntu.json \
  --markdown-out docs/platforms/wsl2_ubuntu.md \
  "$@"

