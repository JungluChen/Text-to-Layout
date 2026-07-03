#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${TEXTLAYOUT_OPENEMS_PREFIX:-$ROOT/.tools/openems-wsl}"
SOURCE="${TEXTLAYOUT_OPENEMS_SOURCE:-$ROOT/.tools/openEMS-Project-wsl}"
PACKAGES=(
  octave octave-control octave-signal octave-io octave-dev
  build-essential cmake git libhdf5-dev libvtk9-dev libvtk9-qt-dev
  libboost-all-dev libcgal-dev libtinyxml-dev qtbase5-dev
  libfftw3-dev libopenmpi-dev
)

install_packages() {
  if [[ "${EUID}" -eq 0 ]]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${PACKAGES[@]}"
  elif sudo -n true 2>/dev/null; then
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${PACKAGES[@]}"
  else
    printf '%s\n' \
      "ERROR: package installation needs root." \
      "From PowerShell run:" \
      "  wsl -u root bash -lc 'apt-get update && apt-get install -y ${PACKAGES[*]}'" \
      "Then rerun: bash scripts/install_openems_wsl.sh --skip-packages" >&2
    exit 2
  fi
}

if [[ "${1:-}" != "--skip-packages" ]]; then
  install_packages
fi

mkdir -p "$(dirname "$SOURCE")" "$(dirname "$PREFIX")"
if [[ -d "$SOURCE/.git" ]]; then
  git -C "$SOURCE" pull --recurse-submodules
  git -C "$SOURCE" submodule update --init --recursive
else
  git clone --recursive https://github.com/thliebig/openEMS-Project.git "$SOURCE"
fi

if ! (cd "$SOURCE" && ./update_openEMS.sh "$PREFIX"); then
  printf '%s\n' \
    "ERROR: openEMS source build failed." \
    "Inspect: $SOURCE/build_*.log" \
    "Verify dependencies, then rerun:" \
    "  cd '$SOURCE' && ./update_openEMS.sh '$PREFIX'" >&2
  exit 3
fi

export PATH="$PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$PREFIX/lib:$PREFIX/lib64:${LD_LIBRARY_PATH:-}"
octave-cli --quiet --eval \
  "addpath('$PREFIX/share/openEMS/matlab'); addpath('$PREFIX/share/CSXCAD/matlab'); InitFDTD('NrTS',0); InitCSX(); disp('openEMS Octave interface: OK');"
openEMS --help >/dev/null

printf '%s\n' \
  "openEMS installed: $PREFIX/bin/openEMS" \
  "CSXCAD installed: $PREFIX/bin/AppCSXCAD" \
  "Octave openEMS path: $PREFIX/share/openEMS/matlab" \
  "Octave CSXCAD path: $PREFIX/share/CSXCAD/matlab"
