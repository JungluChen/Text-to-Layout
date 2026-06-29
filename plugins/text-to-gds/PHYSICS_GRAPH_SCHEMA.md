# Physics Graph Schema

`physics_graph.json` is the Text-to-GDS compiler intermediate representation.
GDS is geometry evidence, not the source of truth for solver or signoff stages.

## Pipeline Position

```text
prompt
-> design_intent.json
-> physics feasibility gate
-> professional layout backend
-> GDS + sidecar.json
-> DRC
-> extraction.json
-> physics_graph.json          ← SOURCE OF TRUTH for all downstream stages
-> solver input generation
-> real solver execution
-> solver agreement
-> review committee
-> signoff report
```

## Schema Version

```json
{
  "schema": "text-to-gds.physics-graph.v1",
  "source_of_truth": "physics_graph.json"
}
```

## Top-Level Fields

| Field | Required | Meaning |
|---|---:|---|
| `schema` | yes | Must be `text-to-gds.physics-graph.v1`. |
| `status` | yes | `ok` or `failed`. |
| `source_gds` | yes | GDS file used for geometric extraction. |
| `source_sidecar` | yes | Sidecar used for semantic ports and device metadata. |
| `source_of_truth` | yes | Must be `physics_graph.json`. |
| `nodes` | yes | Physical devices, conductors, ports, and fields. |
| `edges` | yes | Electrical, capacitive, mutual, and microwave relations. |
| `devices` | yes | Solver-relevant subset of graph nodes. |
| `warnings` | yes | Non-fatal extraction limitations. |

## Node Types

| Type | Description |
|---|---|
| `conductor` | Metal trace or wire |
| `ground` | Ground plane or return conductor |
| `port` | Signal port (RF, DC, flux, pump) |
| `capacitor` | Lumped or distributed capacitance |
| `inductor` | Lumped or distributed inductance |
| `josephson_junction` | Nonlinear Josephson tunneling element |
| `transmission_line` | Distributed microwave transmission line (CPW, etc.) |

## Edge Types

| Type | Description |
|---|---|
| `electrical_connection` | Direct metallic connection |
| `capacitive_coupling` | Capacitive (AC) coupling between nodes |
| `mutual_inductance` | Mutual inductive coupling |
| `microwave_port` | Microwave signal path between port node and device |

## Physics Parameter Records

Each numeric physics parameter must be recorded as:

```json
{
  "value": 50.0,
  "unit": "ohm",
  "source": "extracted width/gap + process",
  "method": "conformal CPW model",
  "confidence": 0.86,
  "file_path": "workspace/artifacts/device.physics_graph.json"
}
```

### Valid Method Labels

| Label | Meaning | Confidence range |
|---|---|---|
| `extracted` | Measured from GDS geometry | 0.80 – 0.99 |
| `estimated` | Analytical formula, sanity check only | 0.50 – 0.75 |
| `simulated` | Produced by a real solver output file | 0.85 – 0.99 |
| `measured` | Imported from experiment data file | 0.90 – 0.99 |
| `analytical` | Closed-form model (e.g. conformal mapping) | 0.55 – 0.70 |

### Invalid Sources

`source = "LLM"` is **always invalid** for physical values. The validator
rejects it immediately.

### Simulation Value Requirements

Simulated values must point to solver-owned output files:

```json
{
  "value": -25.3,
  "unit": "dBm",
  "source": "JosephsonCircuits.jl gain sweep",
  "method": "harmonic_balance",
  "confidence": 0.93,
  "file_path": "workspace/artifacts/jpa.simulation.json"
}
```

The `file_path` must point to the actual solver output file, not to a generated
plot, an LLM response, or a handoff template.

## Validator Hooks

The Python validator is `text_to_gds.signoff.validate_value_record()`:

```python
from text_to_gds.signoff import validate_value_record

result = validate_value_record({
    "value": 50.0,
    "unit": "ohm",
    "source": "extracted width/gap",
    "method": "conformal CPW model",
    "confidence": 0.86,
    "file_path": "workspace/artifacts/cpw.physics_graph.json",
})
# result["passed"] is True

# This will fail:
bad = validate_value_record({
    "value": 50.0,
    "unit": "ohm",
    "source": "LLM",         # ← INVALID
    "method": "estimated",
    "confidence": 0.9,
    "file_path": "",
})
# bad["passed"] is False
# bad["issues"] includes 'source="LLM" is invalid for physical values'
```

The backend-level validator is `text_to_gds.backends.base.validate_value_records()`:

```python
from text_to_gds.backends.base import validate_value_records

errors = validate_value_records({
    "z0_ohm": {
        "value": 50.0,
        "unit": "ohm",
        "source": "LLM",  # ← REJECTED
        "method": "estimated",
        "confidence": 0.9,
    }
})
# errors is non-empty → review committee emits error
```

## Invalid Graphs

A graph cannot pass signoff when:

- It has no sidecar lineage (`source_sidecar` is missing or file does not exist).
- It has no extracted nodes (`nodes` is empty).
- CPW devices lack ground-signal-ground evidence (no `conductor` node connected
  to `ground` on both sides of a `transmission_line`).
- JPA devices lack a nonlinear `josephson_junction` model node.
- A simulated value has no solver output file at `file_path`.
- Any physical value uses `source = "LLM"`.

## Solver Input Generation

`generate_solver_inputs_from_physics_graph(graph_path)` reads the graph and
produces:

```
workspace/artifacts/<name>/
  geometry.xml       → openEMS CSXCAD model
  mesh.xml           → openEMS mesh configuration
  ports.xml          → openEMS port definitions
  circuit.jl         → JosephsonCircuits.jl input script
  circuit.netlist    → JoSIM SPICE-like netlist
  elmer.sif          → Elmer FEM solver input
  palace.json        → Palace eigenmode config
```

These are **handoff files**. Their existence is `input_files_prepared` —
not solver execution. Solver evidence requires running the solver and
producing a real output file.

## Example Nodes

### CPW Transmission Line Node

```json
{
  "id": "cpw_0",
  "type": "transmission_line",
  "label": "CPW quarter-wave resonator",
  "parameters": {
    "z0_ohm": {
      "value": 50.0,
      "unit": "ohm",
      "source": "extracted width=10um gap=6um",
      "method": "conformal CPW model",
      "confidence": 0.86,
      "file_path": "workspace/artifacts/cpw.physics_graph.json"
    },
    "length_um": {
      "value": 7850.0,
      "unit": "um",
      "source": "extracted from GDS bounding box",
      "method": "extracted",
      "confidence": 0.97,
      "file_path": "workspace/artifacts/cpw.sidecar.json"
    },
    "resonance_ghz": {
      "value": 6.0,
      "unit": "GHz",
      "source": "lambda/4 model from extracted length",
      "method": "estimated",
      "confidence": 0.62,
      "file_path": "workspace/artifacts/cpw.physics_graph.json"
    }
  }
}
```

### Josephson Junction Node

```json
{
  "id": "jj_0",
  "type": "josephson_junction",
  "label": "SQUID junction 1",
  "parameters": {
    "ic_ua": {
      "value": 0.658,
      "unit": "uA",
      "source": "junction area * Jc = 2.0 uA/um2",
      "method": "extracted",
      "confidence": 0.92,
      "file_path": "workspace/artifacts/jpa.sidecar.json"
    },
    "lj_ph": {
      "value": 500.0,
      "unit": "pH",
      "source": "Phi0 / (2*pi*Ic)",
      "method": "estimated",
      "confidence": 0.88,
      "file_path": "workspace/artifacts/jpa.physics_graph.json"
    },
    "area_um2": {
      "value": 0.329,
      "unit": "um2",
      "source": "GDS JJ layer polygon area",
      "method": "extracted",
      "confidence": 0.97,
      "file_path": "workspace/artifacts/jpa.sidecar.json"
    }
  }
}
```
