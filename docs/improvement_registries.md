<!-- Moved out of the top-level README to keep it focused. -->

# Improvement Function Registry

The package exposes every item in the 157-point improvement list through
[`text_to_gds.improvements`](src/text_to_gds/improvements.py). The registry maps
each numbered capability to a concrete Python implementation and validates that
the target can be imported.

> **On the capability counts.** The three registries below catalog
> 157 + 146 + 37 = **340 numbered capabilities**, but some entries intentionally
> share an implementation (for example, wafer dicing lanes and alignment marks
> both resolve to `generate_wafer_mask`), so they map to **285 distinct
> callables**. Each `list_*` result reports both numbers
> (`count` and `unique_implementations` / `unique_platform_implementations`).
> `validate_*_registry()` checks that every target is importable and callable;
> it does not assert numerical correctness — that is the job of the test suite
> and the paper-benchmark reproductions.

```python
from text_to_gds.improvements import (
    call_improvement,
    list_improvements,
    validate_improvement_registry,
)

assert list_improvements()["count"] == 157
assert validate_improvement_registry()["passed"]

materials = call_improvement(21)
cpw = call_improvement(31, target_ohm=50.0, epsilon_r=11.45)
```

The implementations are grouped by responsibility:

- [`verification.py`](src/text_to_gds/verification.py): superconducting LVS,
  GDS circuit extraction, SPICE/Julia generation, design and GDS diffs, and
  wafer-mask generation.
- [`fabrication.py`](src/text_to_gds/fabrication.py): wafer runs, oxidation
  recipes, JJ history, wafer-position Ic prediction, process yield, and SEM
  metrology.
- [`physics_extensions.py`](src/text_to_gds/physics_extensions.py): material,
  loss, vortex, magnetic-field, CPW/IDC/coupling, transmission-line, and
  chip-package models.
- [`em_extensions.py`](src/text_to_gds/em_extensions.py): universal 3D stack,
  solver comparison, convergence, uncertainty, rational fitting, reduced-order
  models, feedback, and caching.
- [`quantum_extensions.py`](src/text_to_gds/quantum_extensions.py) and
  [`nonlinear_extensions.py`](src/text_to_gds/nonlinear_extensions.py):
  Hamiltonian/BBQ/Kerr/lifetime and JPA/JTWPA nonlinear models.
- [`measurement_extensions.py`](src/text_to_gds/measurement_extensions.py):
  transport-neutral SCPI drivers, calibration, automated extraction, IQ,
  squeezing, Wigner proxy, and drift analysis.
- [`platform_extensions.py`](src/text_to_gds/platform_extensions.py): cryogenic
  budgets, review/iteration agents, searchable records, publication helpers,
  plugin/API/project generators, permissions, and closed-loop orchestration.

`level: prepared_adapter` means the package creates a complete job or interface
contract but does not claim that an external cloud worker, fabrication tool,
instrument, licensed solver, or literature service executed. Real hardware
control requires an explicitly supplied SCPI/VISA transport and configured
safety limits. SEM-to-GDS comparison requires a registered GDS reference image
at the SEM scale and orientation.

## Next Improvement List

The second 146-item list has a separate callable registry in
[`text_to_gds.next_improvements`](src/text_to_gds/next_improvements.py):

```python
from text_to_gds.next_improvements import (
    call_next_improvement,
    list_next_improvements,
    validate_next_improvement_registry,
)

assert list_next_improvements()["count"] == 146
assert validate_next_improvement_registry()["passed"]

route = call_next_improvement(
    8,
    start_um=(0.0, 0.0),
    end_um=(1000.0, 500.0),
    target_impedance_ohm=50.0,
)
```

New implementation modules:

- [`layout_automation.py`](src/text_to_gds/layout_automation.py): A* microwave
  and CPW routing, ground planes, airbridges, crossovers, package placement,
  floorplanning, hierarchy, labels, and alignment marks.
- [`foundry_extensions.py`](src/text_to_gds/foundry_extensions.py): local PCell
  marketplace, community library, project/notebook templates, foundry PDK
  import, process migration, cost/schedule/inventory, drift, recipes, and
  fabrication reports.
- [`junction_physics.py`](src/text_to_gds/junction_physics.py):
  Ambegaokar-Baratoff, temperature/aging/tunneling/capacitance/subgap,
  quasiparticle/TLS, magnetic degradation, and reliability models.
- [`research_automation.py`](src/text_to_gds/research_automation.py): EM setup
  and surrogates, circuit/network synthesis, JPA/TWPA effects, Lindblad
  dynamics, experiment scheduling and safety, and research-agent contracts.
- [`delivery_extensions.py`](src/text_to_gds/delivery_extensions.py): FAIR/DOI
  data, LaTeX/Overleaf/publication outputs, job queues, Kubernetes/HPC
  manifests, authentication, collaborative editing, SDKs, VS Code, CLI, and
  continuous benchmark artifacts.

Remote instrument control never bypasses authentication, allowlists, safety
interlocks, or the local controller. Kubernetes, HPC, foundry, DOI deposition,
and remote literature features generate validated handoff artifacts but do not
claim that an external service executed.

## Third-Wave Autonomous Scientist Functions

The third-wave registry adds 37 capabilities, bringing the three registries to
340 total functions:

```python
from text_to_gds.third_wave import (
    call_third_wave_improvement,
    list_third_wave_improvements,
    validate_third_wave_registry,
)

registry = list_third_wave_improvements()
assert registry["count"] == 37
assert registry["total_platform_capabilities"] == 340
assert validate_third_wave_registry()["passed"]
```

[`inverse_design.py`](src/text_to_gds/inverse_design.py) implements controlled
EM Jacobians, projected trainable-GDS optimization, exact discrete adjoints for
linear systems, Fourier neural operators, and a multimodal microwave-model
baseline. A backend must expose a deterministic parameter-to-result evaluator;
finite-difference gradients are labelled separately from discrete adjoints.

[`scientist_extensions.py`](src/text_to_gds/scientist_extensions.py) implements
topology invention/evolution, symbolic regression and model selection, complete
cryostat/shielding/vibration/cooldown models, SEM understanding and registration,
yield/root-cause intelligence, literature and claim checks, Bayesian/RL
experiment functions, tapeout/mask/DFM review, leaderboards, reproduction
scores, the multi-agent research lab, and the final autonomous-scientist
orchestration contract.

The final loop cannot authorize fabrication, operate instruments, publish, or
access literature by itself. Those stages require configured adapters, user
authority, source provenance, uncertainty evidence, safety interlocks, and
reviewer approval. “Nobel-level” is treated as an aspiration, not a verifiable
software capability or performance claim.

