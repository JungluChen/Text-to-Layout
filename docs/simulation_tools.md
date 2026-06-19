# Simulation Tools And LJPA References

Text-to-GDS keeps the built-in simulator deterministic for tests, then hands
off deeper circuit analysis to local adapters. The adapters should never claim
success unless the external simulator actually ran on the user's machine.

## Selected Tools

| Tool | Use in Text-to-GDS | Source |
| --- | --- | --- |
| JosephsonCircuits.jl | Frequency-domain harmonic balance for JJ circuits. Text-to-GDS runs a two-port LJPA starter model for `lumped_element_jpa_seed` sidecars and a single-port reflection starter for standalone JJ sidecars. | <https://github.com/kpobrien/JosephsonCircuits.jl> |
| JoSIM | SPICE-like superconducting transient decks for JJ/RCSJ time-domain checks. | <https://github.com/JoeyDelp/JoSIM> |
| ngspice | SPICE CLI handoff for layout-derived starter decks. Text-to-GDS runs a linearized JJ transient deck for standalone junctions and a small-signal two-port RLC deck for LJPA sidecars. | <https://ngspice.sourceforge.io/> |
| PySpice | Future Python orchestration layer for ngspice-backed circuit simulation and plotting. Current support reports module availability only. | <https://github.com/PySpice-org/PySpice> |
| Magic VLSI | Layout extraction/DRC handoff before SPICE netlist simulation. Text-to-GDS writes and runs a Magic TCL script for GDS import, extraction, and SPICE export when Magic is installed. | <http://opencircuitdesign.com/magic/> |
| scikit-rf | RF network backend. When installed, exported Touchstone `.s2p` files are loaded by a real `skrf.Network` for port/Z0 review. | <https://github.com/scikit-rf/scikit-rf> |
| openEMS | Real EC-FDTD EM extraction. When the local openEMS runtime is present, the adapter runs a microstrip-port FDTD model and returns S11/S21, effective permittivity, a Z0 estimate, and E-field VTK dumps. | <https://github.com/thliebig/openEMS> |
| Optuna | Real optimizer backend. When installed, a TPE study runs the constrained gain/bandwidth/frequency/P1dB objective (deterministic grid fallback otherwise). | <https://github.com/optuna/optuna> |
| scqubits | Real Hamiltonian solver. When installed, the adapter instantiates a `Transmon`/`TunableTransmon`, diagonalizes it, and returns energy levels, anharmonicity, and a flux/charge spectrum. | <https://github.com/scqubits/scqubits> |
| QCoDeS | Real measurement runtime. When installed, the adapter builds a station/experiment and records a mock-VNA S-parameter sweep into a genuine SQLite dataset (no hardware touched). | <https://github.com/microsoft/Qcodes> |
| Qiskit Metal | Real design build. When importable, the adapter constructs a `QDesign` + `QComponent` and renders GDS. On Windows/Python 3.12 it skips cleanly because PySide2 has no matching wheel (use conda or Python <=3.10). | <https://github.com/qiskit-community/qiskit-metal> |
| KQCircuits | Reference point for KLayout-based superconducting quantum layout libraries and parameterized elements. | <https://github.com/iqm-finland/KQCircuits> |

## Installation Notes

Text-to-GDS does not vendor Julia, JosephsonCircuits.jl, or JoSIM into git. Use
the local installer to place portable tools under `.tools/`, or install them
globally and make them available on PATH:

```powershell
.\scripts\install_toolchain.ps1
```

Check availability from this project:

```powershell
py -3 -m uv run python -c "from text_to_gds.adapters import list_simulation_adapters; print(list_simulation_adapters())"
```

Manual JosephsonCircuits.jl path:

```powershell
$env:JULIA_DEPOT_PATH = "$PWD\.tools\julia-depot"
.tools\julia-1.12.6\bin\julia.exe -e 'using Pkg; Pkg.add(url="https://github.com/kpobrien/JosephsonCircuits.jl")'
```

Manual JoSIM path:

```powershell
# Install a release binary, then verify:
.tools\josim-v2.7\bin\josim-cli.exe --help
```

Global install alternatives:

```powershell
julia -e 'using Pkg; Pkg.add(url="https://github.com/kpobrien/JosephsonCircuits.jl")'
josim --help
ngspice -v
magic -version
```

Validated Windows-local installs:

```powershell
# ngspice through MSYS2
C:\msys64\usr\bin\pacman.exe -Sy --noconfirm mingw-w64-ucrt-x86_64-ngspice

# Magic VLSI extracted from Ubuntu packages into .tools/ for WSL execution
wsl -e sh -lc 'cd /mnt/c/Users/justi/Desktop/Layout/text-to-gds; mkdir -p .tools/magic-wsl-download .tools/magic-wsl-root; cd .tools/magic-wsl-download; apt-get download magic libtcl8.6 tcl8.6 libglu1-mesa libopengl0; for f in *.deb; do dpkg -x "$f" ../magic-wsl-root; done'
```

The project discovers `C:\msys64\ucrt64\bin\ngspice.exe` and
`scripts\magic_wsl.py` automatically. Magic may report `executed_with_warnings`
with the generic `scmos` tech because the superconducting layer map needs a
process-specific Magic tech file for calibrated extraction.

## Adapter Execution

When installed, adapters can be run through `run_simulation`:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py simulate workspace\artifacts\ljpa_seed.sidecar.json --simulator josim
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py simulate workspace\artifacts\ljpa_seed.sidecar.json --simulator ngspice
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py simulate workspace\artifacts\ljpa_seed.sidecar.json --simulator JosephsonCircuits.jl --analysis-mode auto --target-frequency-ghz 5.0 --target-bandwidth-mhz 500
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py magic-extract workspace\artifacts\ljpa_seed.gds
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py rf-export workspace\artifacts\ljpa_seed.sidecar.simulation.json --output-name ljpa_seed
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py openems-project workspace\artifacts\ljpa_seed.sidecar.json --output-name ljpa_seed
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py hamiltonian-model workspace\artifacts\ljpa_seed.sidecar.json --jc-ua-per-um2 2.0 --output-name ljpa_seed
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py measurement-plan workspace\artifacts\ljpa_seed.sidecar.json --simulation-path workspace\artifacts\ljpa_seed.sidecar.simulation.json --output-name ljpa_seed
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py research-optimize workspace\artifacts\ljpa_seed.sidecar.json --n-trials 16 --target-gain-db 20 --target-bandwidth-mhz 500 --min-p1db-dbm -100 --output-name ljpa_seed
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py design-workflow "Design a 5 Ghz LJPA with wilde bandwidth" --output-name ljpa_josim.gds --simulator josim
```

If the executable is missing, the adapter status is `skipped`. If a custom
binary or wrapper should be used, pass `--adapter-executable`.

The current JoSIM adapter runs a real transient starter deck and parses the CSV
columns such as `time`, `V(BJJ)`, and `P(BJJ)`.

The ngspice adapter runs a real generated `.ngspice.cir` deck when the
executable is installed. It writes `.ngspice.dat`, `.ngspice.log`, and
`.ngspice.json`, then parses numeric output rows for plotting. For standalone
JJ sidecars, the deck linearizes the junction as `Lj` plus optional shunt
capacitance. For LJPA sidecars, the deck uses a small-signal two-port RLC
starter with 50 ohm source/load terms, layout-derived `Lj`, target-frequency
capacitance, and optional coupling/resonator capacitance overrides. Treat this
as a fast circuit-iteration model, not extracted SPICE signoff.

Each `run_simulation` response includes a `physical_performance` section. For
LJPA sidecars, it records input/output ports, target/estimated gain, 3 dB
bandwidth, loaded Q, pump current, resonator/coupling capacitance, quantum
noise temperature, estimated saturation/P1dB power, and dc-SQUID flux tuning.
For via-chain sidecars, it records stage count, input/output ports, estimated
total resistance, and open-chain topology status.

## SQUID Flux Tuning

`lumped_element_jpa_seed` uses the `dc_squid_pair` PCell. The built-in
low-loop-inductance model treats the SQUID as a flux-tunable Josephson
inductor:

```text
Ic_eff(Phi) = Ic0 * sqrt(cos(pi * Phi/Phi0)^2 + d^2 * sin(pi * Phi/Phi0)^2)
Lj(Phi) = Phi0 / (2 * pi * Ic_eff(Phi))
f0(Phi) = 1 / (2 * pi * sqrt(Lj(Phi) * C_res))
```

Inputs:

- `--flux-bias-phi0`: operating flux in units of `Phi0`.
- `--squid-asymmetry`: `abs(Ic1 - Ic2) / (Ic1 + Ic2)`.
- `--flux-period-current-ma`: coil current for one flux quantum, when known.
- `--flux-mutual-inductance-ph`: optional mutual inductance alternative.

Example:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py design-workflow "Design a 5 GHz LJPA with flux tuning" --output-name flux_tuned_ljpa.gds --jc-ua-per-um2 2.0 --flux-bias-phi0 0.25 --squid-asymmetry 0.05 --flux-period-current-ma 2.0
```

This writes `physical_performance.flux_tuning` with `operating_point`,
`tuning_range_ghz`, and a flux sweep table. The quick and scientific plots use
the flux tuning curve when it is present.

The Magic VLSI adapter runs a generated `.magic.tcl` script when the executable
is installed. The script imports GDS, loads the selected top cell, runs
`extract all`, and attempts `ext2spice` export. It writes `.magic.json`, plus
`.magic.spice` and `.magic.ext` when Magic produces them. Without a
process-specific Magic tech file, treat the output as a local handoff scaffold,
not a calibrated parasitic-extraction result.

The JosephsonCircuits.jl adapter runs a real `hbsolve` starter model. With
`analysis_mode="auto"`, an LJPA sidecar generated by `lumped_element_jpa_seed`
selects the two-port model and records:

- `frequencies_ghz`
- `s_parameters_db.s11_db`
- `s_parameters_db.s21_db`
- `s_parameters_db.s12_db`
- `s_parameters_db.s22_db`
- `peak_s21_gain_db`
- `peak_s21_frequency_ghz`
- `center_s21_gain_db`
- `bandwidth_3db_mhz`
- `target_errors`

Standalone JJ sidecars fall back to the single-port reflection model and record
`reflection_gain_db`, `peak_gain_db`, `center_gain_db`, and
`bandwidth_3db_mhz`. Both models derive `Lj` from layout area and `Jc`. The LJPA
model derives a target resonator capacitance from the requested center
frequency unless `--resonator-capacitance-ff` is supplied, uses 50 ohm ports,
and defaults coupling capacitance to 5 percent of the target capacitance with a
minimum of 5 fF. Full gain/noise signoff from extracted CPW/JJ/coupling
networks is still future work.

Every simulation run writes a Python-rendered `.simulation.png`:

- JosephsonCircuits.jl multiport: S11/S21/S12/S22 gain curves.
- JosephsonCircuits.jl single-port: reflection gain.
- JoSIM: first parsed transient column pair.
- ngspice: first parsed output column pair.
- Ideal JJ: compact `Ic`/`Lj` summary.

Every simulation run also writes a scientific plot/data package:

- `.scientific.png` for high-resolution review.
- `.scientific.svg` for vector documents.
- `.scientific.csv` for the plotted numeric table.
- `.scientific.json` for provenance and metrics.

You can regenerate that package from any saved simulation JSON:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py scientific-plot workspace\artifacts\ljpa_seed.sidecar.simulation.json --title "LJPA S-parameter Review"
```

Run local parameter sweeps without external simulators:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py sweep workspace\artifacts\ljpa_seed.sidecar.json --sweep-parameter jc_ua_per_um2 --start 1 --stop 4 --points 7
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py sweep workspace\artifacts\ljpa_seed.sidecar.json --sweep-parameter target_bandwidth_mhz --start 100 --stop 800 --points 8 --target-frequency-ghz 5
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py sweep workspace\artifacts\ljpa_seed.sidecar.json --sweep-parameter flux_bias_phi0 --start -0.5 --stop 0.5 --points 101 --target-frequency-ghz 5 --squid-asymmetry 0.05
```

Sweep outputs include `.json`, `.png`, `.svg`, and `.csv`. Treat them as
layout-derived first-order studies until replaced by measured or extracted
external simulator data.

## Research Integration Execution

The research adapters execute the upstream library directly when it is installed and
report `status: skipped` (with an install hint) otherwise — they never claim a result the
external tool did not produce. Verify which run on your machine:

```powershell
py -3 -m uv run pytest tests/test_research_execution.py -q
```

Install the pure-Python research stack (optuna, scikit-rf, qcodes, scqubits):

```powershell
py -3 -m uv sync --extra research
```

openEMS ships as a Windows binary release with cp310/cp311 wheels (no PyPI package and no
cp312 wheel), so Text-to-GDS runs it through a dedicated Python 3.11 interpreter:

```powershell
# 1. download + unpack the official release into .tools/
#    (.tools/openEMS-v0.0.36/openEMS holds the DLLs and python/*.whl)
# 2. create a 3.11 venv and install the matching wheels:
py -3 -m uv venv --python 3.11 .tools/openems-venv
py -3 -m uv pip install --python .tools/openems-venv/Scripts/python.exe `
  .tools/openEMS-v0.0.36/openEMS/python/CSXCAD-0.6.3-cp311-cp311-win_amd64.whl `
  .tools/openEMS-v0.0.36/openEMS/python/openEMS-0.0.36-cp311-cp311-win_amd64.whl `
  numpy h5py matplotlib
```

The openEMS adapter discovers `.tools/openems-venv` and `.tools/openEMS*/openEMS`
automatically, or honors `TEXT_TO_GDS_OPENEMS_PYTHON` and `TEXT_TO_GDS_OPENEMS_BIN`.

qiskit-metal cannot be pip-installed on Windows/Python 3.12 because PySide2 has no matching
wheel; use conda or a Python <=3.10 environment. The adapter builds a real `QDesign` and
renders GDS wherever `qiskit_metal` is importable.

### JPA analysis and the scientific report

Two tools turn the JosephsonCircuits.jl harmonic balance into the advanced parametric
amplifier figures:

```powershell
# Real pump-power sweep -> gain vs pump, P1dB, noise temperature, squeezing, stability.
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py jpa-analysis workspace\artifacts\ljpa_jc.sidecar.json --jc-ua-per-um2 6.8 --target-frequency-ghz 5.0

# Ten-figure composite: Layout, S11/S21, Gain, Bandwidth, Flux tuning, Pump sweep,
# P1dB, Noise temperature, Squeezing, Stability (real panels labelled josephsoncircuits_real).
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py scientific-report workspace\artifacts\ljpa_jc.sidecar.json --jc-ua-per-um2 6.8
```

The JPA pump sweep runs one `hbsolve` per pump current using a layout-derived single-port
reflection model (resonance ~6% above the pump, fine ~1.6 MHz frequency grid). Quantum
efficiency comes from the harmonic-balance `QE`/`QEideal` outputs, noise temperature is the
quantum limit divided by efficiency, squeezing is the ideal degenerate-paramp value from the
peak gain, and the oscillation threshold is the pump current that maximizes small-signal
gain. Reaching a target gain (e.g. 20 dB) is a design task: the Optuna adapter can drive it.

## Academic Anchors

- Mutus et al., "Design and characterization of a lumped element single-ended
  superconducting microwave parametric amplifier with on-chip flux bias line",
  reports tunable 5-7 GHz amplification, gain-bandwidth product above 500 MHz,
  and an on-chip flux-bias line. Source: <https://arxiv.org/abs/1308.1376>
- Elo et al., "Broadband lumped-element Josephson parametric amplifier with
  single-step lithography", reports 20 dB gain with 95 MHz bandwidth around
  5 GHz using a flux-pumped JPA. Source: <https://arxiv.org/abs/1812.07621>
- Suri et al., "Impedance-Engineered Josephson Parametric Amplifier with
  Single-Step Lithography", reports impedance engineering with a lumped-element
  series LC circuit and 18 dB gain over 400 MHz bandwidth centered around
  5.3 GHz. Source: <https://arxiv.org/abs/2507.09298>
- JosephsonCircuits.jl cites use for gain/noise performance simulation of
  ultra-low-noise amplifiers such as Josephson traveling-wave parametric
  amplifiers. Source: <https://github.com/kpobrien/JosephsonCircuits.jl>
- Nation et al. describe dc-SQUIDs as two Josephson junctions in a loop and use
  a flux-tunable SQUID critical current/inductance model for superconducting
  microwave circuits. Source: <https://ar5iv.labs.arxiv.org/html/1103.0835>

## Parameter Contract

The layout sidecar and extraction report must expose any parameter that can
change circuit performance:

- material system and layer name
- metal thickness and kinetic inductance assumptions
- junction width, height, area, and critical-current density
- CPW trace width, gap, ground width, and length
- shunt capacitance and dielectric assumptions
- via size, enclosure, and routing layer transitions
- line angle, pitch, turn count, and electrical length

The planner should ask for missing process and target data before making
signoff-style claims.
