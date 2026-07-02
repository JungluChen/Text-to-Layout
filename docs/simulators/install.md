# Simulator installation

One command bootstraps everything that can be bootstrapped:

```bash
make setup-simulators     # = python scripts/bootstrap_simulators.py
make check-simulators     # = python scripts/check_simulators.py
make demo-jpa
```

Windows without `make`: run the `python scripts/...` commands directly, or
`./scripts/install_simulators.ps1`.

## Roles (do not mix them up)

| Tool | Question it answers |
| --- | --- |
| FasterCap/FastCap | "Does the drawn geometry have the target capacitance?" (EM/electrostatic extraction) |
| JoSIM / PSCAN2 / WRspice | "Does a circuit with these L/C/JJ values behave as expected in time domain?" |

A circuit simulator can never substitute for capacitance extraction, and an
installed simulator never means physics is verified. `PHYSICS_VERIFIED`
requires a real extraction **and** a real simulation, both within declared
tolerances.

## Local tool directory

Everything lands in the git-ignored `.tools/` directory:

```
.tools/
├── josim/bin/josim-cli[.exe]     # canonical JoSIM location
├── pscan2/                        # reserved (PSCAN2 is a Python package)
├── wrspice/bin/wrspice[.exe]      # place a manual WRspice install here
├── build/                         # download/build scratch space
└── simulators.json                # machine-local install manifest
```

No simulator binaries or source trees are ever committed, and none live under
`src/`. `TEXTLAYOUT_TOOLS_DIR` relocates the whole directory.

## JoSIM (primary, auto-installed)

Detection order — the same in `scripts/check_simulators.py` and in the
runtime adapters:

1. `TEXTLAYOUT_JOSIM` (path to the executable)
2. `.tools/josim/bin/josim-cli`
3. `.tools/josim/bin/josim`
4. `josim-cli` on PATH
5. `josim` on PATH

`scripts/install_josim.py` tries, in order: adopt an existing
`.tools/josim-*/bin` unpack → download the platform asset from the official
MIT-licensed releases (https://github.com/JoeyDelp/JoSIM/releases) → build
from source with git + CMake (Linux/macOS; prints the exact package-manager
commands when prerequisites are missing) → print exact manual steps
(Windows). Every install is verified by actually running the binary.

Manual override:

```bash
export TEXTLAYOUT_JOSIM=/opt/josim/bin/josim-cli        # POSIX
$env:TEXTLAYOUT_JOSIM = "C:\tools\josim\josim-cli.exe"  # PowerShell
```

## PSCAN2 (optional, manual)

Detection order: `TEXTLAYOUT_PSCAN2` → importable `pscan2` Python module →
conda/mamba hint. Install per http://pscan2sim.org/ (typically into a conda
environment), then either run textlayout from that environment or point
`TEXTLAYOUT_PSCAN2` at that environment's Python. This project does not
attempt a blind automatic install; absence is recorded as
`manual_install_required` and never blocks JoSIM setup or the demo.

## WRspice (optional, manual)

Detection order: `TEXTLAYOUT_WRSPICE` → `.tools/wrspice/bin/wrspice` →
`.tools/wrspice/bin/wrspice64` → PATH. Download from
http://wrcad.com/xictools/ or build https://github.com/wrcad/xictools; this
project does not download or redistribute WRspice binaries (see
[licenses.md](licenses.md)). Absence is `manual_install_required` and never
blocks anything.

## Strict mode

`TEXTLAYOUT_STRICT_SIMULATORS=1` (or `--strict`) makes the bootstrap/checker
exit nonzero when a required simulator (default: JoSIM; extend with
`--require josim,pscan2,wrspice`) is missing. The `textlayout prompt`
command has its own `--strict-simulation` flag with the same spirit.

## Docker / devcontainer

```bash
make docker-simulators   # builds docker/simulators.Dockerfile
```

The image installs build tools, syncs the project, bootstraps JoSIM, gates
the build on a strict JoSIM check, runs the JPA demo, and prints the final
availability table. The `.devcontainer/` uses the same Dockerfile and runs
`make check-simulators` after creation.
