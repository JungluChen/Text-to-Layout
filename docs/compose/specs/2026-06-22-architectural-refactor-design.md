# Text-to-GDS Architectural Refactor: AI Superconducting Design Copilot

## [S1] Problem Statement

The current Text-to-GDS project attempts to be a complete custom EDA tool with 100+ modules, custom PCells, manual physics formulas, and simulated results. This approach:

1. **Duplicates decades of EDA development** - reinventing CPW calculators, JJ geometry, transmon models
2. **Risks physics credibility** - analytical approximations presented as simulation results
3. **Lacks fabrication readiness** - custom PCells miss real process constraints
4. **Creates maintenance burden** - maintaining 100+ modules is unsustainable

**Goal**: Refactor into an AI orchestration layer that controls professional superconducting design tools.

## [S2] Architecture Overview

### Target Architecture

```text
                    User Prompt
                        │
                        ▼
            ┌───────────────────────┐
            │   AI Design Copilot   │
            │   (orchestration)     │
            └───────────┬───────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Layout Layer  │ │ Physics Layer │ │ Sim Layer     │
│               │ │               │ │               │
│ KQCircuits    │ │ extraction.py │ │ openEMS       │
│ gdsfactory    │ │ physics_*.py  │ │ Josephson     │
│ KLayout       │ │ solver_*.py   │ │ Circuits.jl   │
└───────────────┘ └───────────────┘ └───────────────┘
```

### Core Principle

The AI layer never:
- Draws polygons
- Invents physics formulas
- Fabricates simulation results
- Replaces validated EDA tools

The AI layer always:
- Translates natural language → design intent
- Selects validated components
- Configures parameters
- Calls real solvers
- Interprets results
- Proposes parameter updates

## [S3] Layout Backend Design

### Technology Selection

**Primary**: gdsfactory + KQCircuits hybrid
- gdsfactory: Infrastructure (GDS I/O, KLayout integration, rendering)
- KQCircuits: Validated superconducting PCells (transmon, JJ, CPW, resonator)

### PCell Replacement Strategy

| Current Custom PCell | Replacement | Action |
|---------------------|-------------|--------|
| `cpw_straight` | KQCircuits `CoplanarWaveguideStraight` | Delete custom, wrap KQC |
| `cpw_quarter_wave_resonator` | KQCircuits `QuarterWaveResonator` | Delete custom, wrap KQC |
| `manhattan_josephson_junction` | Keep + enhance with KQCircuits JJ metadata | Keep (unique features) |
| `jj_ic_calibration_array` | Keep (no KQC equivalent) | Keep |
| `dc_squid_pair` | KQCircuits `SQUID` (evaluate) | Evaluate replacement |
| `via_chain_monitor` | Keep (test structure) | Keep |
| `lumped_element_jpa_seed` | Keep (composition PCell) | Keep |
| `meander_inductor` | KQCircuits `MeanderInductor` | Evaluate replacement |
| `flux_bias_line` | Keep (no KQC equivalent) | Keep |

### Design Intent Schema

```json
{
  "device": "transmon|jpa|resonator|squid|twpa",
  "parameters": {
    "frequency_ghz": 6.0,
    "coupling_mhz": 100,
    "ej_ec_ratio": 50
  },
  "technology": "kqcircuits|gdsfactory",
  "process": "ncu_alox_2026|mit_ll_sfq|ibm_nb"
}
```

### Technology Abstraction

```python
class SuperconductingTechnology:
    """Technology-aware PCell selector."""
    
    def select_junction(self, params: dict) -> PCell:
        """Select validated JJ PCell based on technology."""
        pass
    
    def select_resonator(self, params: dict) -> PCell:
        """Select validated resonator PCell."""
        pass
    
    def select_transmon(self, params: dict) -> PCell:
        """Select validated transmon PCell."""
        pass
```

## [S4] Physics Extraction Redesign

### ExtractedQuantity Schema

```python
@dataclass
class ExtractedQuantity:
    value: float
    unit: str
    source: str          # "analytical", "em_simulation", "circuit_simulation", "measured"
    method: str          # "conformal_mapping", "openEMS_fDTD", "josephsonCircuits_hb"
    validity_range: str  # "initial_design", "verified", "signoff"
    confidence: float    # 0.0 - 1.0
```

### Extraction Hierarchy

| Level | Source | Use Case | Confidence |
|-------|--------|----------|------------|
| `estimated` | Analytical formulas | Initial design, feasibility | 0.3-0.6 |
| `extracted` | GDS geometry + process rules | Layout verification | 0.5-0.7 |
| `simulated` | EM/circuit solver | Design optimization | 0.7-0.9 |
| `measured` | Lab measurement | Final validation | 0.9-1.0 |

### Provenance Chain

```json
{
  "Lj": {
    "value": 3387.5,
    "unit": "pH",
    "source": "analytical",
    "method": "josephson_inductance_from_Ic",
    "validity_range": "estimated",
    "confidence": 0.5,
    "dependencies": ["Ic"],
    "note": "Requires measured Ic for signoff"
  }
}
```

### Key Principle

Never mix estimated and simulated values. Always label the source.

## [S5] Simulation Redesign

### SolverResult Schema

```python
@dataclass
class SolverResult:
    status: str          # "executed" | "skipped" | "failed"
    reason: str          # Why skipped/failed
    solver: str          # "openEMS" | "josephsonCircuits" | "scqubits"
    output_path: str     # Path to solver output file
    parsed_data: dict    # Parsed results
    execution_time_s: float
```

### Solver Adapter Contract

```python
class SolverAdapter:
    def execute(self, input_data: dict) -> SolverResult:
        """
        Rules:
        1. Check if solver executable is available
        2. If not: return status="skipped", reason="solver_not_installed"
        3. Generate input files (netlist, XML, JSON)
        4. Run solver via subprocess
        5. If returncode != 0: return status="failed", reason=stderr
        6. Parse output files
        7. Validate output exists and is parseable
        8. Return status="executed" with parsed data
        """
```

### EM Solver Priority (openEMS first)

```python
EM_SOLVERS = {
    "planar": ["openEMS", "palace", "meep", "elmer"],
    "volumetric": ["palace", "openEMS", "meep", "elmer"],
    "lumped": ["openEMS", "palace", "meep", "elmer"],
}
```

### Circuit Solvers

```python
CIRCUIT_SOLVERS = {
    "nonlinear": ["josephsonCircuits", "sqcircuit"],
    "quantum": ["scqubits", "josephsonCircuits"],
    "transient": ["josim", "ngspice"],
}
```

### Placeholder Rule

If a solver is not installed, return `status="skipped"`. Never create placeholder curves or fake data.

## [S6] AI Orchestration Layer

### Pipeline

```text
User: "Design a 6 GHz transmon with 100 MHz coupling"
        │
        ▼
AI extracts design_intent.json
        │
        ▼
Select technology (KQCircuits)
        │
        ▼
Select validated PCells:
  - TransmonCross (from KQCircuits)
  - CoplanarWaveguide (from KQCircuits)
  - LaunchPad (from KQCircuits)
        │
        ▼
Configure parameters:
  - junction_area: 0.05 um²
  - cpw_width: 10 um
  - cpw_gap: 6 um
  - coupling_length: 200 um
        │
        ▼
Generate GDS
        │
        ▼
Run extraction:
  - JJ: Ic, Lj, Cj (analytical)
  - CPW: Z0, eps_eff (conformal mapping)
        │
        ▼
Run EM simulation:
  - openEMS: S-parameters, coupling
        │
        ▼
Run circuit simulation:
  - JosephsonCircuits: Hamiltonian, Kerr
        │
        ▼
Compare target vs result:
  - frequency_error = |6.0 - 5.97| / 6.0 = 0.5%
  - coupling_error = |100 - 98| / 100 = 2%
        │
        ▼
If error > threshold:
  AI proposes parameter update
  Loop back to configure
        │
        ▼
Output:
  - GDS file
  - Extraction table with provenance
  - Simulation results with solver metadata
  - Review report
```

### AI Responsibilities

1. Translate natural language → design intent
2. Select technology and PCells
3. Configure parameters
4. Orchestrate simulation pipeline
5. Interpret results
6. Propose parameter updates

### AI Never

1. Draws polygons
2. Invents physics formulas
3. Fabricates simulation results
4. Replaces validated EDA tools

## [S7] Repository Refactor

### Code to DELETE

- `cpw_straight` PCell (replaced by KQCircuits)
- `cpw_quarter_wave_resonator` PCell (replaced by KQCircuits)
- `estimate_physical_performance()` deprecated code in simulation.py
- Placeholder/fake simulation results
- Manual physics formulas that duplicate existing packages

### Code to KEEP

- `server.py` (MCP server)
- `rendering.py` (KLayout renderer)
- `process.py` (PDK/process stack)
- `extraction.py` (geometry extraction)
- `drc.py` (KLayout DRC)
- `adapters.py` (solver adapters)
- `em_solvers.py` (EM routing)
- `solver_agreement.py` (cross-validation)
- `ai_scientist.py` (orchestration)
- `feasibility_gate.py` (pre-check)
- `report.py`, `figures.py`, `plots.py` (visualization)
- `research.py` (workflow orchestration)

### Code to ADD

- `src/text_to_gds/layout/technology.py` - Technology abstraction
- `src/text_to_gds/layout/kqcircuits_wrapper.py` - KQCircuits integration
- `src/text_to_gds/physics/extraction_provenance.py` - Provenance tracking
- `src/text_to_gds/simulation/solver_adapter.py` - Strict solver adapter base class
- `src/text_to_gds/simulation/openems_adapter.py` - openEMS adapter
- `src/text_to_gds/simulation/josephsoncircuits_adapter.py` - JosephsonCircuits adapter
- `src/text_to_gds/ai/design_intent.py` - Natural language → design intent
- `src/text_to_gds/ai/copilot.py` - Main orchestration loop

### Folder Restructuring

```text
src/text_to_gds/
├── __init__.py
├── server.py              # MCP server (keep)
├── layout/                # NEW: Layout backend
│   ├── technology.py      # Technology abstraction
│   ├── kqcircuits_wrapper.py
│   ├── gdsfactory_wrapper.py
│   └── pcells/            # Custom PCells that survive
├── physics/               # NEW: Physics layer
│   ├── extraction.py      # Geometry extraction (keep)
│   ├── extraction_provenance.py  # Provenance tracking
│   ├── cpw_physics.py     # Analytical CPW (keep)
│   ├── junction_physics.py # JJ physics (keep)
│   └── superconductivity.py # Material physics (keep)
├── simulation/            # NEW: Simulation layer
│   ├── solver_adapter.py  # Base adapter class
│   ├── openems_adapter.py
│   ├── josephsoncircuits_adapter.py
│   ├── scqubits_adapter.py
│   └── solver_agreement.py # Cross-validation (keep)
├── ai/                    # NEW: AI orchestration
│   ├── design_intent.py
│   ├── copilot.py
│   └── parameter_update.py
├── drc.py                 # KLayout DRC (keep)
├── process.py             # PDK/process stack (keep)
├── rendering.py           # KLayout renderer (keep)
├── adapters.py            # Solver adapter registry (keep)
├── em_solvers.py          # EM routing (keep)
├── ai_scientist.py        # Orchestration (keep)
├── feasibility_gate.py    # Pre-check (keep)
├── report.py              # Report generation (keep)
├── figures.py             # Publication figures (keep)
└── ...                    # Other modules to evaluate
```

### Dependency Selection

**Required**:
- gdsfactory >= 8.0 (GDS I/O, KLayout integration)
- klayout >= 0.29 (GDS manipulation, DRC)
- KQCircuits (validated superconducting PCells)
- openEMS (EM simulation)
- JosephsonCircuits.jl (nonlinear circuit simulation)

**Optional**:
- scqubits (quantum Hamiltonian)
- pyEPR (HFSS integration)
- pyaedt (Ansys integration)
- Palace/Elmer (FEM simulation)

### Migration Plan

**Phase 1: Foundation** (Week 1-2)
- Create `layout/technology.py` abstraction
- Integrate KQCircuits as primary PCell source
- Create `simulation/solver_adapter.py` base class
- Create `physics/extraction_provenance.py`

**Phase 2: Core Integration** (Week 3-4)
- Replace `cpw_straight` with KQCircuits wrapper
- Replace `cpw_quarter_wave_resonator` with KQCircuits wrapper
- Implement strict openEMS adapter
- Implement strict JosephsonCircuits adapter

**Phase 3: AI Orchestration** (Week 5-6)
- Implement `ai/design_intent.py` (NLP → intent)
- Implement `ai/copilot.py` (orchestration loop)
- Implement `ai/parameter_update.py` (optimization)

**Phase 4: Cleanup** (Week 7-8)
- Delete replaced custom PCells
- Delete deprecated code
- Update documentation
- Run full test suite

### Required Tests

1. **Technology selection tests**: Verify correct PCell selection based on technology
2. **Provenance tests**: Verify extraction quantities have correct metadata
3. **Solver adapter tests**: Verify `status="skipped"` when solver not installed
4. **Integration tests**: Verify end-to-end pipeline from prompt to GDS
5. **Regression tests**: Verify existing functionality preserved

## [S8] Success Criteria

1. **Layout**: Generated GDS uses validated KQCircuits PCells
2. **Physics**: Every quantity has provenance metadata
3. **Simulation**: All results from real solver execution (or `status="skipped"`)
4. **AI**: Natural language → design intent → GDS pipeline works end-to-end
5. **Tests**: Full test suite passes
6. **Documentation**: Architecture diagram and migration guide complete
