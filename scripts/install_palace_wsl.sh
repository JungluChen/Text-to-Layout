#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${TEXTLAYOUT_PALACE_SOURCE:-$ROOT/.tools/palace-source}"

if [[ "${PALACE_BUILD:-0}" != "1" ]]; then
  cat <<'EOF'
Palace is intentionally not built by default because it requires PETSc, MFEM,
MPI, HYPRE, MUMPS, and substantial compile time.

Install the lightweight preparation stack first:
  wsl -u root bash -lc 'apt-get update && apt-get install -y gmsh python3-meshio git cmake build-essential'

To attempt the official Palace source build:
  PALACE_BUILD=1 bash scripts/install_palace_wsl.sh

If that build fails, inspect Palace's current official build documentation and
the CMake output. Do not mark full-chip evidence executed until a `palace`
binary runs and a result file is parsed.
EOF
  exit 0
fi

if [[ -d "$SOURCE/.git" ]]; then
  git -C "$SOURCE" pull --recurse-submodules
else
  git clone --recursive https://github.com/awslabs/palace.git "$SOURCE"
fi

cmake -S "$SOURCE" -B "$SOURCE/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$SOURCE/build" --parallel
printf 'Palace build completed. Locate the binary under %s/build and set TEXTLAYOUT_PALACE.\n' "$SOURCE"
