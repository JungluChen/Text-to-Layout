# Simulation Tools And LJPA References

Text-to-GDS keeps the built-in simulator deterministic for tests, then hands
off deeper circuit analysis to local adapters. The adapters should never claim
success unless the external simulator actually ran on the user's machine.

## Selected Tools

| Tool | Use in Text-to-GDS | Source |
| --- | --- | --- |
| JosephsonCircuits.jl | Frequency-domain harmonic balance for JJ circuits. Text-to-GDS runs a single-port reflection starter model and records gain-vs-frequency data. | <https://github.com/kpobrien/JosephsonCircuits.jl> |
| JoSIM | SPICE-like superconducting transient decks for JJ/RCSJ time-domain checks. | <https://github.com/JoeyDelp/JoSIM> |
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
```

## Adapter Execution

When installed, adapters can be run through `run_simulation`:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py simulate workspace\artifacts\ljpa_seed.sidecar.json --simulator josim
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py simulate workspace\artifacts\ljpa_seed.sidecar.json --simulator JosephsonCircuits.jl --target-frequency-ghz 5.0 --target-bandwidth-mhz 500
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py design-workflow "Design a 5 Ghz LJPA with wilde bandwidth" --output-name ljpa_josim.gds --simulator josim
```

If the executable is missing, the adapter status is `skipped`. If a custom
binary or wrapper should be used, pass `--adapter-executable`.

The current JoSIM adapter runs a real transient starter deck and parses the CSV
columns such as `time`, `V(BJJ)`, and `P(BJJ)`. The current
JosephsonCircuits.jl adapter runs a real `hbsolve` single-port reflection
starter model, deriving `Lj` from layout area and `Jc`, deriving default shunt
capacitance from the requested center frequency when none is provided, and
recording `frequencies_ghz`, `reflection_gain_db`, `peak_gain_db`,
`center_gain_db`, and `bandwidth_3db_mhz`. A full multiport gain/noise model
from extracted CPW/JJ/coupling networks is still future signoff work.

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
