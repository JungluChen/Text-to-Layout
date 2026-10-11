"""Isolated SQcircuit Hamiltonian worker; output is raw, not canonical acceptance.

Invoke with an explicitly selected optional interpreter, request.json and a new
output filename. The product-side runner and canonical assessment remain separate.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any


def validate_plan(plan: dict[str, Any]) -> dict[str, float]:
    """Validate the file boundary before importing optional numerical packages."""
    expected = {
        "schema_name": "textlayout.sqcircuit-lc-plan.v1",
        "method": "SQcircuit Hamiltonian + numpy.linalg.eigh",
        "sqcircuit_version": "1.0.0",
        "source_revision": "7cdc826a63224a8fb860362224a4a530e80aa1d7",
        "truncations": [10, 20, 30],
        "levels": 6,
        "reference_limit_hz": 1.0,
        "scaled_residual_limit": 1e-12,
        "hermiticity_limit": 1e-14,
    }
    if set(plan) != set(expected) | {"request"}:
        raise ValueError("Unexpected plan fields")
    for key, value in expected.items():
        if type(plan[key]) is not type(value) or plan[key] != value:
            raise ValueError(f"Unsupported plan field: {key}")
    bounds = {
        "capacitance_f": (8e-14, 1e-13),
        "inductance_h": (6e-8, 1e-7),
        "branch_capacitance_f": (1e-20, 1e-15),
    }
    request = plan["request"]
    if not isinstance(request, dict) or set(request) != set(bounds):
        raise ValueError("Explicit SI element fields required")
    result: dict[str, float] = {}
    for name, (low, high) in bounds.items():
        value = request[name]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"Invalid SI input: {name}")
        result[name] = float(value)
    return result


def execute(input_path: Path, output_path: Path) -> None:
    """Retain raw matrices/eigenpairs and identity without asserting convergence."""
    raw = input_path.read_bytes()
    plan = json.loads(raw)
    request = validate_plan(plan)
    if output_path.exists():
        raise FileExistsError(output_path)
    if importlib.metadata.version("SQcircuit") != "1.0.0":
        raise ValueError("SQcircuit 1.0.0 is required")
    sq = importlib.import_module("SQcircuit")
    np = importlib.import_module("numpy")
    sq.set_unit_freq("GHz")
    rows = []
    c, inductance, branch = (request[k] for k in (
        "capacitance_f", "inductance_h", "branch_capacitance_f"
    ))
    for size in plan["truncations"]:
        circuit = sq.Circuit({(0, 1): [
            sq.Capacitor(c, "F"),
            sq.Inductor(inductance, "H", cap=sq.Capacitor(branch, "F")),
        ]})
        circuit.set_trunc_nums([size])
        matrix = circuit.hamiltonian().full()
        if matrix.shape != (size, size) or not np.isfinite(matrix).all():
            raise ValueError("Invalid Hamiltonian shape or nonfinite data")
        values, vectors = np.linalg.eigh(matrix)
        values, vectors = values[:6], vectors[:, :6]
        if not np.isfinite(values).all() or not np.isfinite(vectors).all():
            raise ValueError("Nonfinite eigenpair data")
        rows.append({
            "truncation": size,
            "resolved_capacitance_f": float(circuit.C[0, 0]),
            "hamiltonian_rad_s_real": matrix.real.tolist(),
            "hamiltonian_rad_s_imag": matrix.imag.tolist(),
            "eigenvalues_rad_s": values.tolist(),
            "eigenvectors_real": vectors.real.tolist(),
            "eigenvectors_imag": vectors.imag.tolist(),
        })
    if sq.__file__ is None:
        raise ValueError("SQcircuit source path unavailable")
    source = Path(sq.__file__).parent
    report = {
        "schema_name": "textlayout.sqcircuit-lc-raw.v1",
        "method": plan["method"],
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "inputs": request,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "versions": {name: importlib.metadata.version(name) for name in (
            "SQcircuit", "numpy", "scipy", "qutip", "torch", "sympy"
        )},
        "source_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                          for name in ("circuit.py", "elements.py", "units.py")},
        "rows": rows,
        "numerical_acceptance": "NOT_EVALUATED",
    }
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


if __name__ == "__main__":
    execute(Path(sys.argv[1]), Path(sys.argv[2]))
