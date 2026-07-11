"""Publish compact Palace 0.17 benchmark evidence for committing.

    uv run python scripts/publish_palace_v017_benchmark.py \
        [--run out/palace_resonator_v017] [--check]

Copies only compact summaries, hashes, and short logs from a validated run
into ``examples/solver_benchmarks/palace_cpw_quarter_wave_v017/``. Large raw
solver output (adapted meshes, ParaView fields, full postpro trees) is never
published. ``--check`` verifies the committed packet still matches the run
outputs it claims to summarise (used by CI and the README drift gate).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.evidence.canonical import load_canonical  # noqa: E402

PACKET = ROOT / "examples" / "solver_benchmarks" / "palace_cpw_quarter_wave_v017"
COPIED = (
    "toolchain.json",
    "run_manifest.json",
    "mode_tracking.json",
    "convergence.json",
    "canonical_evidence.json",
)
SOLVER_BACKED = {"SIMULATION_EXECUTED", "CONVERGENCE_FAILED", "PHYSICS_VERIFIED"}


def _csv_text(header: list[str], rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def _amr_summary(convergence: dict[str, Any]) -> str:
    rows = [
        [
            record["tag"],
            record["palace_iteration"],
            record["element_count"],
            record["degrees_of_freedom"],
            record["polynomial_order"],
            record["tracked_mode_index"],
            record["tracked_frequency_ghz"],
            record["global_error_indicator_percent"],
            record["substrate_participation"],
            record["vacuum_participation"],
            record["energy_normalization_error_percent"],
            record["runtime_seconds"],
        ]
        for record in convergence["amr_iterations"]
    ]
    return _csv_text(
        [
            "tag",
            "palace_iteration",
            "element_count",
            "nedelec_dof",
            "polynomial_order",
            "tracked_mode_index",
            "tracked_frequency_ghz",
            "global_error_indicator_percent",
            "substrate_participation",
            "vacuum_participation",
            "energy_normalization_error_percent",
            "runtime_seconds",
        ],
        rows,
    )


def _sweep_summary(convergence: dict[str, Any], category: str) -> str:
    rows = [
        [
            point["sweep"],
            point["value"],
            point["unit"],
            point["frequency_ghz"],
            point["mode_index"],
            point["substrate_participation"],
            point["vacuum_participation"],
            point["mesh_sha256"][:16],
            point["resolved_config_sha256"][:16],
            point["runtime_seconds"],
        ]
        for point in convergence["sweep_points"]
        if point["category"] == category
    ]
    return _csv_text(
        [
            "sweep",
            "value",
            "unit",
            "frequency_ghz",
            "mode_index",
            "substrate_participation",
            "vacuum_participation",
            "mesh_sha256_prefix",
            "resolved_config_sha256_prefix",
            "runtime_seconds",
        ],
        rows,
    )


def _readme(evidence: Any, manifest: dict[str, Any], convergence: dict[str, Any]) -> str:
    amr = manifest["amr"]
    initial = manifest["initial_mesh"]
    numerical = [
        r
        for r in convergence["verification_report"]["numerical_domain_results"]
    ]
    physical = [r for r in convergence["verification_report"]["physical_sensitivity"]]

    def _sens(rows: list[dict[str, Any]]) -> str:
        return "\n".join(
            "| {} | {} | {} | {} |".format(
                row["name"],
                f"{row['frequency_sensitivity_percent']:.4f}%"
                if row["frequency_sensitivity_percent"] is not None
                else "-",
                f"{row['substrate_participation_sensitivity_percent']:.4f}%"
                if row["substrate_participation_sensitivity_percent"] is not None
                else "-",
                {True: "PASS", False: "FAIL", None: "reported only"}[row["passed"]],
            )
            for row in rows
        )

    return (
        "# Quarter-wave CPW resonator — Palace 0.17 WSL/Spack AMR run\n\n"
        "A real Palace 0.17.0 execution through the public\n"
        "`textlayout simulate palace-resonator` command: one validated Gmsh\n"
        "simplex mesh, Palace-native adaptive mesh refinement, mode tracking by\n"
        "frequency continuity and regional energy similarity (never spatial\n"
        "field overlap), three numerical-domain sweeps, and separately reported\n"
        "physical sensitivity studies.\n\n"
        f"| | |\n|---|---|\n"
        f"| Status | **`{evidence.status.value}`** |\n"
        f"| Tracked frequency | `{evidence.extracted_value}` GHz |\n"
        f"| Solver | Palace `{evidence.solver_version}` |\n"
        f"| Executable SHA-256 | `{evidence.solver_executable_sha256}` |\n"
        f"| Git commit | `{evidence.git_commit}` |\n"
        f"| Timestamp | {evidence.timestamp} |\n"
        f"| AMR iterations | {amr['accepted_iterations']} ({amr['stop_reason']}) |\n"
        f"| Elements | {initial['element_count']} -> {amr['final_element_count']} |\n"
        f"| ND DOF (final) | {amr['final_degrees_of_freedom']} |\n"
        f"| Final global error indicator | "
        f"{amr['final_global_error_indicator_percent']:.4f}% |\n"
        f"| Initial mesh SHA-256 | `{initial['sha256']}` |\n"
        f"| Final adapted mesh SHA-256 | `{manifest['final_adapted_mesh']['sha256']}` |\n\n"
        "## Numerical-domain convergence (gated)\n\n"
        "| sweep | frequency sensitivity | substrate participation sensitivity | result |\n"
        "| --- | ---: | ---: | --- |\n"
        f"{_sens(numerical)}\n\n"
        "## Physical sensitivity (reported, never gated)\n\n"
        "| study | frequency sensitivity | substrate participation sensitivity | result |\n"
        "| --- | ---: | ---: | --- |\n"
        f"{_sens(physical)}\n\n"
        "Physical sensitivity is a property of the device and stack assumptions;\n"
        "it is not numerical convergence and never fails it.\n\n"
        "## Why this is not PHYSICS_VERIFIED\n\n"
        "There is no independent reference artifact for this design. The\n"
        "requested 6 GHz design target is a quasi-static model, not a\n"
        "reference; a fully converged run is therefore limited to\n"
        "`SIMULATION_EXECUTED` by the evidence contract.\n\n"
        "## Regeneration\n\n"
        "```bash\n"
        "uv run textlayout simulate palace-resonator --out out/palace_resonator_v017\n"
        "uv run python scripts/promote_palace_v017.py --run out/palace_resonator_v017\n"
        "uv run python scripts/publish_palace_v017_benchmark.py\n"
        "```\n\n"
        "Raw solver output (adapted mesh, full postpro trees) stays under\n"
        "`out/palace_resonator_v017/raw/` and is never committed; every retained\n"
        "artifact is identified here by SHA-256.\n"
    )


def build_packet(run: Path) -> dict[str, str]:
    """Return {relative filename: content or source path marker}."""
    evidence = load_canonical(run / "canonical_evidence.json")
    if evidence.status.value not in SOLVER_BACKED:
        raise SystemExit(
            f"refusing to publish non-solver-backed evidence ({evidence.status.value})"
        )
    problems = evidence.verify_output_hashes(run)
    if problems:
        raise SystemExit("run output hashes no longer verify: " + "; ".join(problems))
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    convergence = json.loads((run / "convergence.json").read_text(encoding="utf-8"))
    rendered = {
        "README.md": _readme(evidence, manifest, convergence),
        "amr_summary.csv": _amr_summary(convergence),
        "numerical_domain_summary.csv": _sweep_summary(convergence, "numerical_domain"),
        "physical_sensitivity_summary.csv": _sweep_summary(convergence, "physical_parameter"),
    }
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="out/palace_resonator_v017")
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)
    run = (ROOT / args.run).resolve()

    if args.check:
        if not PACKET.is_dir():
            print("[FAIL] no committed palace_cpw_quarter_wave_v017 packet", file=sys.stderr)
            return 1
        problems: list[str] = []
        for name in (*COPIED, "provenance.json", "test_environment.json"):
            if not (PACKET / name).is_file():
                problems.append(f"missing {name}")
        evidence = load_canonical(PACKET / "canonical_evidence.json")
        if evidence.solver_version != "0.17.0":
            problems.append(f"packet solver_version {evidence.solver_version!r}")
        if evidence.status.value not in SOLVER_BACKED:
            problems.append(f"packet status {evidence.status.value} is not solver-backed")
        if run.is_dir() and (run / "canonical_evidence.json").is_file():
            fresh = build_packet(run)
            for name, content in fresh.items():
                committed = (PACKET / name).read_text(encoding="utf-8")
                if committed != content:
                    problems.append(f"{name} drifted from the run it summarises")
        for problem in problems:
            print(f"[FAIL] {problem}", file=sys.stderr)
        if problems:
            return 1
        print("committed Palace 0.17 benchmark packet is current")
        return 0

    rendered = build_packet(run)
    PACKET.mkdir(parents=True, exist_ok=True)
    for name in COPIED:
        shutil.copy2(run / name, PACKET / name)
    for name, content in rendered.items():
        (PACKET / name).write_text(content, encoding="utf-8", newline="\n")
    _write_test_environment(run)
    provenance_source = (
        ROOT / "examples" / "solver_benchmarks" / "palace_cpw_quarter_wave" / "provenance.json"
    )
    shutil.copy2(provenance_source, PACKET / "provenance.json")
    print(f"published compact packet to {PACKET.relative_to(ROOT)}")
    return 0


def _write_test_environment(run: Path) -> None:
    """Write the packet's test_environment.json (machine + timing facts).

    Prefers a measured ``test_environment.json`` written next to the run;
    otherwise synthesises one from the toolchain, install, and smoke records
    plus the committed baseline environment.
    """
    measured = run / "test_environment.json"
    if measured.is_file():
        shutil.copy2(measured, PACKET / "test_environment.json")
        return
    baseline = ROOT / "out" / "baseline" / "environment.json"
    base = json.loads(baseline.read_text(encoding="utf-8")) if baseline.is_file() else {}
    toolchain = json.loads((run / "toolchain.json").read_text(encoding="utf-8"))
    smoke = ROOT / "out" / "toolchain" / "palace_smoke" / "result.json"
    smoke_runtime = "unknown"
    if smoke.is_file():
        payload = json.loads(smoke.read_text(encoding="utf-8"))
        seconds = payload.get("runtime_seconds")
        if isinstance(seconds, (int, float)):
            smoke_runtime = f"{seconds:.0f} s"
    cpu = base.get("cpu", {})
    environment = {
        "os": base.get("os", "unknown"),
        "wsl": base.get("wsl_distribution", "unknown"),
        "cpu": (
            f"{cpu.get('model', 'unknown')} ({cpu.get('logical_cores', '?')} logical cores)"
            if cpu
            else "unknown"
        ),
        "ram": f"{base.get('ram_gb_wsl', '?')} GB (WSL)",
        "gmsh": toolchain.get("gmsh", {}).get("version", "unknown"),
        "install_duration": "recorded in out/toolchain/palace_install.json",
        "smoke_runtime": smoke_runtime,
    }
    (PACKET / "test_environment.json").write_text(
        json.dumps(environment, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
