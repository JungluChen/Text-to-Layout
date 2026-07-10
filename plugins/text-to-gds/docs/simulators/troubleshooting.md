# Simulator troubleshooting

Run `python scripts/check_simulators.py` after every fix; it prints the
authoritative availability table.

## CMake missing (JoSIM source build)

Symptom: `[josim] cannot build from source; missing tools: cmake`.

```bash
sudo apt-get install -y cmake            # Debian/Ubuntu
sudo dnf install cmake                   # Fedora/RHEL
brew install cmake                       # macOS
winget install Kitware.CMake             # Windows
```

## Compiler missing

Symptom: missing tool `c++`.

```bash
sudo apt-get install -y build-essential  # Debian/Ubuntu
sudo dnf groupinstall "Development Tools"
xcode-select --install                    # macOS
```

On Windows, prefer the pre-built release zip instead of compiling: the
installer downloads it automatically when GitHub is reachable.

## Windows path issues

- `TEXTLAYOUT_JOSIM` must point at the **file** (`...\josim-cli.exe`), not
  the folder.
- PowerShell: `$env:TEXTLAYOUT_JOSIM = "C:\path\to\josim-cli.exe"` affects
  only the current session; use System Properties → Environment Variables to
  persist.
- Paths with spaces are fine — the scripts never split on whitespace — but
  quote them in your shell.
- If `python` resolves to the Microsoft Store stub, install Python from
  python.org or use `py -3 scripts\check_simulators.py`.

## JoSIM build failed

1. Read the CMake/compiler error above the `[josim] source build failed`
   line — the most common causes are an outdated CMake (< 3.15) or missing
   C++17 support.
2. Delete the scratch tree and retry: remove `.tools/build/JoSIM`.
3. Skip building entirely: download the release zip/tar from
   https://github.com/JoeyDelp/JoSIM/releases and place the binary at
   `.tools/josim/bin/`, or set `TEXTLAYOUT_JOSIM`.
4. The failure is recorded in `.tools/simulators.json` as `install_failed`
   with the reason; `check_simulators.py` surfaces it.

## PSCAN2: conda missing

PSCAN2 is distributed for conda-style environments (http://pscan2sim.org/).
Install Miniconda/Miniforge first, create an environment per the official
instructions, then either run textlayout from that environment or set
`TEXTLAYOUT_PSCAN2` to that environment's `python`. Until then the status
`manual_install_required` is correct and harmless — the demo still runs and
reports PSCAN2 inputs as prepared, never executed.

## WRspice: manual install required

Expected. WRspice binaries are distributed by Whiteley Research
(http://wrcad.com/xictools/) and this project does not mirror them. Install
it, then place/symlink the executable at `.tools/wrspice/bin/wrspice` or set
`TEXTLAYOUT_WRSPICE`. Sanity-check with `wrspice --version` yourself first.

## Environment variable overrides

```bash
# POSIX
export TEXTLAYOUT_JOSIM=/opt/josim/bin/josim-cli
export TEXTLAYOUT_PSCAN2=/opt/conda/envs/pscan2/bin/python
export TEXTLAYOUT_WRSPICE=/usr/local/xictools/bin/wrspice
export TEXTLAYOUT_TOOLS_DIR=/data/textlayout-tools     # relocate .tools/
export TEXTLAYOUT_STRICT_SIMULATORS=1                  # fail hard when missing
```

```powershell
$env:TEXTLAYOUT_JOSIM = "C:\tools\josim\josim-cli.exe"
$env:TEXTLAYOUT_WRSPICE = "C:\tools\xictools\bin\wrspice.exe"
```

Priority is always: explicit `--executable` argument → environment variable →
`.tools/<sim>/bin` → PATH.

## Real simulator vs mock simulator

The test suite uses **mock executables** (tiny scripts that emit synthetic
waveforms) to prove the run → parse → resonance-check plumbing without any
simulator installed. Those runs are test fixtures, not physics:

- A mock run can never appear in your artifacts — mocks exist only inside
  pytest temp directories.
- A real JoSIM run on the LC template produces at best
  `JOSIM_RESONANCE_CHECKED` (circuit-level resonance vs the analytical
  `f0 = 1/(2π√(LC))`).
- `PHYSICS_VERIFIED` additionally requires real geometry-level capacitance
  extraction (FasterCap/FastCap) within tolerance. An installed simulator
  alone proves nothing about the layout.
