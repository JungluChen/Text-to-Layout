"""Pinned two-case CircuitQ LC numerical acceptance; no product/EM claim."""

from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import inspect
import json
import math
import platform
import sys
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "references/circuitq/lc-plan.json"
PLAN_SHA256 = "8a08917451830ec6c44306af70d75cdd3942dce7709922828e93e68381421b53"


def assess(rows, plan, reference):
    expected = [(d, plan["half_domain_sigma"]) for d in plan["dimensions"]]
    expected += [(plan["expanded_dimension"], plan["expanded_half_domain_sigma"])]
    if [(r["dimension"], r["half_domain_sigma"]) for r in rows] != expected:
        raise ValueError("Missing/reordered grid or domain samples")
    if not math.isfinite(reference) or reference <= 0:
        raise ValueError("Invalid reference frequency")
    for row in rows:
        if row["resolved_dimension"] != row["dimension"]:
            raise ValueError("Unexpected resolved dimension")
        for key in (
            "frequency_hz",
            "anharmonicity_hz",
            "scaled_residual",
            "hermiticity_relative",
            "matrix_similarity_relative",
        ):
            if not math.isfinite(row[key]):
                raise ValueError("Nonfinite numerical output")
        if row["frequency_hz"] <= 0 or any(
            row[k] < 0
            for k in ("scaled_residual", "hermiticity_relative", "matrix_similarity_relative")
        ):
            raise ValueError("Invalid frequency or norm")
        if row["matrix_similarity_relative"] >= 1e-12:
            raise ValueError("SI/natural matrix mismatch")
    fine, prior, expanded = rows[-2], rows[-3], rows[-1]
    metrics = dict(
        frequency_relative=abs(fine["frequency_hz"] / reference - 1),
        refinement_relative=abs(fine["frequency_hz"] - prior["frequency_hz"]) / reference,
        anharmonicity_over_frequency=abs(fine["anharmonicity_hz"]) / reference,
        domain_relative=abs(fine["frequency_hz"] - expanded["frequency_hz"]) / reference,
        scaled_residual=max(r["scaled_residual"] for r in rows),
        hermiticity_relative=max(r["hermiticity_relative"] for r in rows),
    )
    return metrics, all(v <= plan[k + "_limit"] for k, v in metrics.items())


def execute(plan):
    import circuitq as cq
    import networkx as nx
    import numpy as np
    import scipy.sparse.linalg as sla

    if importlib.metadata.version("circuitq") != "1.2.1":
        raise ValueError("Expected pinned CircuitQ 1.2.1")
    cases = []
    for case in plan["cases"]:
        c_f, l_h = case["capacitance_f"], case["inductance_h"]
        h = plan["reference_h_j_s"]
        hbar = h / (2 * math.pi)
        sigma = math.sqrt(hbar * math.sqrt(l_h / c_f) / 2)
        reference = 1 / (2 * math.pi * math.sqrt(l_h * c_f))
        rows = []
        for dimension, extent in [(d, plan["half_domain_sigma"]) for d in plan["dimensions"]] + [
            (plan["expanded_dimension"], plan["expanded_half_domain_sigma"])
        ]:
            graph = nx.MultiGraph()
            graph.add_edge(0, 1, element="C")
            graph.add_edge(0, 1, element="L")
            circuit = cq.CircuitQ(graph, ground_nodes=[0], natural_units=False)
            names = [str(p) for p in circuit.h_parameters]
            if names != ["C_{01}", "L_{010}"]:
                raise ValueError("Unexpected parameter ordering")
            matrix = circuit.get_numerical_hamiltonian(
                dimension, grid_length=extent * sigma, parameter_values=[c_f, l_h]
            )
            si_matrix = matrix.copy()
            energy_scale = circuit.hbar_si * 1e9
            flux_scale = circuit.hbar_si / (2 * circuit.e)
            natural = cq.CircuitQ(graph, ground_nodes=[0], natural_units=True)
            capacitance_nat = c_f * energy_scale / (2 * circuit.e) ** 2
            inductance_nat = l_h * energy_scale / flux_scale**2
            matrix = natural.get_numerical_hamiltonian(
                dimension,
                grid_length=extent * sigma / flux_scale,
                parameter_values=[capacitance_nat, inductance_nat],
            )
            similarity = float(sla.norm(matrix * energy_scale - si_matrix) / sla.norm(si_matrix))
            if not math.isfinite(similarity) or similarity >= 1e-12:
                raise ValueError("SI/natural matrix mismatch")
            values, vectors = natural.get_eigensystem(n_eig=5)
            if not np.all(np.isfinite(values)) or not np.all(np.isfinite(vectors)):
                raise ValueError("Nonfinite eigensystem")
            if np.max(np.abs(np.imag(values))) != 0:
                raise ValueError("Complex eigenvalues")
            norm = float(sla.norm(matrix))
            herm = float(sla.norm(matrix - matrix.getH()) / norm)
            residual = max(
                float(
                    np.linalg.norm(matrix @ vectors[:, i] - values[i] * vectors[:, i])
                    / (norm * np.linalg.norm(vectors[:, i]))
                )
                for i in range(5)
            )
            energies = np.real(values) * energy_scale
            f = float((energies[1] - energies[0]) / h)
            alpha = float((energies[2] - 2 * energies[1] + energies[0]) / h)
            rows.append(
                dict(
                    dimension=dimension,
                    energy_scale_j=energy_scale,
                    matrix_similarity_relative=similarity,
                    natural_capacitance=capacitance_nat,
                    natural_inductance=inductance_nat,
                    resolved_dimension=circuit.n_dim,
                    half_domain_sigma=extent,
                    grid_length_wb=float(circuit.grid_length),
                    parameter_names=names,
                    parameter_values=circuit.parameter_values,
                    energies_j=energies.tolist(),
                    frequency_hz=f,
                    anharmonicity_hz=alpha,
                    scaled_residual=residual,
                    hermiticity_relative=herm,
                    upstream_hbar=circuit.hbar_si,
                )
            )
        metrics, passed = assess(rows, plan, reference)
        cases.append(
            dict(
                inputs=case,
                reference_frequency_hz=reference,
                sigma_wb=sigma,
                rows=rows,
                metrics=metrics,
                passed=passed,
            )
        )
    return dict(
        cases=cases,
        passed=all(c["passed"] for c in cases),
        upstream_core_sha256=hashlib.sha256(
            Path(inspect.getfile(cq.CircuitQ)).read_bytes()
        ).hexdigest(),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    raw = PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("Benchmark plan changed")
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "plan.json").write_bytes(raw)
    report = dict(
        plan_sha256=PLAN_SHA256,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        platform=platform.platform(),
        python=platform.python_version(),
        command=sys.argv,
        dependencies=sorted(
            f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()
        ),
        canonical_evidence_promoted=False,
    )
    try:
        report.update(execute(json.loads(raw)))
    except Exception as exc:
        report.update(passed=False, error=f"{type(exc).__name__}: {exc}")
    (args.out / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
