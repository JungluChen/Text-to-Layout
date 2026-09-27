# Run an explicit transmon Hamiltonian

**Document class: MANUAL_DOCUMENTATION.** Requires the optional `quantum`
extra. This is a Python API example; no new CLI or MCP method is claimed.

Install the package with its quantum extra, then run:

```python
from textlayout.solvers.scqubits_adapter import prepare_scqubits_input, execute_scqubits

prepared = prepare_scqubits_input(
    {"ic_a": 4e-8, "capacitance_f": 80e-15, "ng": 0.0, "ncut": 30, "n_evals": 6},
    "out/transmon",
)
result = execute_scqubits(prepared)
print(result.to_dict())
```

Inputs are critical current in amperes and capacitance in farads. Supply
measured or extracted values with their own provenance for a real device;
the numbers above are an explicit demonstration, not measurements.
EJ/h and EC/h are calculated in GHz using the legacy adapter's constants.
No default EJ/EC ratio is assumed. A real installed scqubits library executes
`Transmon.eigenvals`; `scqubits_result.json` retains energies, transitions,
input hash, version, parameters, model lineage and warnings.

For these inputs, scqubits 4.1.0 on macOS produced f01 approximately
5.950794 GHz and anharmonicity approximately -268.236 MHz in two identical
runs. This is executed model evidence, not independent validation. Increase
charge cutoff and compare against an independent reference before any stronger
claim. A spectrum with |anharmonicity| below 10 MHz is rejected. EJ/EC below 10
retains the existing charge-regime warning and `transmon_regime=false`.
Missing scqubits is skipped; missing/non-finite/non-positive SI inputs fail.

Model reference: [scqubits Transmon documentation](https://scqubits.readthedocs.io/en/latest/guide/qubits/transmon.html).
The actual geometry and junction extraction remain separate prerequisites.
