#!/usr/bin/env bash
set -euo pipefail

# Idempotent WSL2 Ubuntu bootstrap for the supported Python/core workflow.
# Optional solver builds are opt-in because they are large and platform-specific.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WINDOWS_MOUNT_PREFIX="/mnt/"
NATIVE_ROOT="${TEXTLAYOUT_WSL_NATIVE_ROOT:-${HOME}/.local/share/textlayout}"
UV_VERSION="${TEXTLAYOUT_BOOTSTRAP_UV_VERSION:-0.12.1}"
DRY_RUN=0
SKIP_APT=0
QUICK=0
WITH_OPENEMS=0
WITH_PALACE=0
WITH_CIRCUIT_SOLVERS=0

usage() {
  cat <<'EOF'
Usage: bash scripts/bootstrap_wsl.sh [options]

Options:
  --dry-run               Print the deterministic plan; change nothing.
  --skip-apt              Do not install Ubuntu packages.
  --quick                 Run focused smoke tests instead of the full suite.
  --with-openems          Build openEMS under WSL-native storage (large).
  --with-palace           Attempt the official Palace source build (very large).
  --with-circuit-solvers  Run the JoSIM/FasterCap/PSCAN2/WRspice bootstrap.
  -h, --help              Show this help.

Environment:
  TEXTLAYOUT_WSL_NATIVE_ROOT       Native ext4 root for tools/builds.
  TEXTLAYOUT_BOOTSTRAP_UV_VERSION  Pinned uv bootstrap version (default 0.12.1).
EOF
}

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --skip-apt) SKIP_APT=1 ;;
    --quick) QUICK=1 ;;
    --with-openems) WITH_OPENEMS=1 ;;
    --with-palace) WITH_PALACE=1 ;;
    --with-circuit-solvers) WITH_CIRCUIT_SOLVERS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'ERROR: unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

print_command() {
  printf ' +'
  printf ' %q' "$@"
  printf '\n'
}

run() {
  print_command "$@"
  if ((DRY_RUN == 0)); then
    "$@"
  fi
}

run_shell() {
  printf ' + %s\n' "$1"
  if ((DRY_RUN == 0)); then
    bash -lc "$1"
  fi
}

printf '%s\n' \
  'Text-to-Layout WSL2 bootstrap' \
  "repository: $REPO_ROOT" \
  "native root: $NATIVE_ROOT" \
  "uv version: $UV_VERSION" \
  "dry run: $DRY_RUN"

if ((DRY_RUN == 0)); then
  if [[ ! -e /proc/sys/fs/binfmt_misc/WSLInterop ]] \
    && [[ -z "${WSL_INTEROP:-}" ]] \
    && [[ "$(uname -r)" != *[Mm]icrosoft* ]]; then
    printf '%s\n' \
      'ERROR: this bootstrap must run inside Ubuntu on WSL.' \
      'From PowerShell, enter `wsl`, then rerun the command.' >&2
    exit 2
  fi

  WSL_RELEASE="$(uname -r)"
  WSL_VERSION=1
  if [[ "$WSL_RELEASE" == *WSL2* ]] || [[ "$WSL_RELEASE" == *microsoft-standard* ]]; then
    WSL_VERSION=2
  fi
  printf 'WSL version: %s\n' "$WSL_VERSION"
  printf 'WSL distro: %s\n' "${WSL_DISTRO_NAME:-unknown}"
  printf 'architecture: %s\n' "$(uname -m)"
  printf 'filesystem: %s\n' "$(findmnt -n -o FSTYPE -T "$REPO_ROOT" 2>/dev/null || echo unknown)"
  if [[ "$REPO_ROOT" == "${WINDOWS_MOUNT_PREFIX}"* ]]; then
    printf '%s\n' \
      'WARNING: the checkout is under /mnt. Layout generation is supported there,' \
      "but heavy FEM sources/builds are redirected to WSL-native storage: $NATIVE_ROOT" >&2
  fi
else
  printf '%s\n' 'WSL detection: deferred by --dry-run'
fi

if ((SKIP_APT == 0)); then
  APT_PACKAGES=(
    build-essential
    ca-certificates
    curl
    file
    git
    python3
    python3-pip
    python3-venv
  )
  if ((DRY_RUN == 1)); then
    run sudo apt-get update
    run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${APT_PACKAGES[@]}"
  elif [[ "$EUID" -eq 0 ]]; then
    run apt-get update
    run env DEBIAN_FRONTEND=noninteractive apt-get install -y "${APT_PACKAGES[@]}"
  elif command -v sudo >/dev/null 2>&1; then
    run sudo apt-get update
    run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${APT_PACKAGES[@]}"
  else
    printf 'ERROR: apt packages require root or sudo. Rerun with --skip-apt after installing prerequisites.\n' >&2
    exit 2
  fi
fi

UV_ENV="$NATIVE_ROOT/bootstrap-uv"
run mkdir -p "$NATIVE_ROOT" "$REPO_ROOT/out/platform/wsl2"
if [[ ! -x "$UV_ENV/bin/uv" ]]; then
  run python3 -m venv "$UV_ENV"
  run "$UV_ENV/bin/python" -m pip install --disable-pip-version-check "uv==$UV_VERSION"
fi
export PATH="$UV_ENV/bin:$PATH"

cd "$REPO_ROOT"
run uv sync --frozen --dev
run_shell 'uv run textlayout doctor --json > out/platform/wsl2/doctor.json'
run uv run textlayout doctor
run uv run textlayout prompt \
  "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap" \
  --out out/platform/wsl2/idc_prompt
run uv run textlayout verify examples/benchmarks/01_idc_0p6pf/layout.json

if ((QUICK == 1)); then
  run uv run pytest tests/textlayout_suite/test_cli_end_to_end.py
else
  run uv run pytest
fi

export TEXTLAYOUT_TOOLS_DIR="$NATIVE_ROOT/tools"
if ((WITH_CIRCUIT_SOLVERS == 1)); then
  run uv run python scripts/bootstrap_simulators.py --tools-dir "$TEXTLAYOUT_TOOLS_DIR"
fi

if ((WITH_OPENEMS == 1)); then
  export TEXTLAYOUT_OPENEMS_PREFIX="$TEXTLAYOUT_TOOLS_DIR/openems-wsl"
  export TEXTLAYOUT_OPENEMS_SOURCE="$NATIVE_ROOT/sources/openEMS-Project"
  run bash scripts/install_openems_wsl.sh
fi

if ((WITH_PALACE == 1)); then
  export TEXTLAYOUT_PALACE_SOURCE="$NATIVE_ROOT/sources/palace"
  run env PALACE_BUILD=1 bash scripts/install_palace_wsl.sh
fi

printf '%s\n' \
  'WSL bootstrap completed.' \
  'Optional solver absence remains an honest MISSING/SKIPPED_SOLVER_ABSENT state.'
