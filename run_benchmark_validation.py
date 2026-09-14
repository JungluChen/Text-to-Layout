"""Reproducible local prompt sweep; paper parity is a separate, explicit gate.

Usage: python run_benchmark_validation.py --out out/audit/benchmark
See BENCHMARK_SPEC.md for the fixed population, metrics, and comparison limits.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "benchmarks" / "audit" / "literature.json"
THRESHOLD_PERCENT = 0.1


def source_tree_sha256() -> str:
    """Hash supported product source including new files not yet committed."""
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src" / "textlayout").rglob("*.py")):
        if "_legacy" in path.parts:
            continue
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    for name in ("pyproject.toml", "uv.lock"):
        digest.update(name.encode() + b"\0" + (ROOT / name).read_bytes())
    return digest.hexdigest()


def default_cases() -> list[dict[str, Any]]:
    """Fixed engineering population. Paper frequencies are scalar seeds only."""
    cases: list[dict[str, Any]] = []

    def add(component: str, prompt: str, key: str, value: float, source: str) -> None:
        cases.append(dict(id=f"case_{len(cases) + 1:03d}", component=component,
                          prompt=prompt, target_key=key, target=value, source=source))

    for cap in (0.2, 0.4, 0.6, 0.8):
        for width in (2, 4):
            for gap in (2, 3):
                add("IDC", f"Create a {cap} pF IDC on silicon at 6 GHz with "
                    f"{width} um finger width and {gap} um min gap",
                    "capacitance_pf", cap, "local engineering grid")
    for impedance in (30, 40, 50, 60):
        for gap in (2, 4, 6, 8):
            add("CPW", f"Create a {impedance} ohm CPW on silicon at 6 GHz "
                f"with {gap} um min gap", "impedance_ohm", impedance, "local engineering grid")
    for inductance in (1, 2, 3, 4):
        for turns in (2, 3, 4, 5):
            add("SpiralInductor", f"Create a {inductance} nH spiral inductor with "
                f"{turns} turns, 4 um trace width and 2 um spacing",
                "inductance_nh", inductance, "local engineering grid")
    refs = json.loads(SOURCE.read_text())
    frequencies = [(f, "SQuADDS Figure 1 scalar seed; geometry is NOT replicated")
                   for f in refs["squadds"]["frequency_seeds_ghz"]]
    frequencies += [(r["measured_ghz"], "Ye Table I scalar seed; geometry is NOT replicated")
                    for r in refs["ye"]["rows"]]
    frequencies += [(f, "local engineering grid") for f in (4, 4.5, 5, 5.5, 6, 8)]
    for frequency, source in frequencies:
        add("QuarterWaveResonator", f"Create a {frequency} GHz quarter-wave resonator "
            "on silicon", "frequency_ghz", frequency, source)
    return cases


def relative_error(actual: float, reference: float) -> float:
    if not math.isfinite(actual) or not math.isfinite(reference) or reference <= 0:
        raise ValueError("A finite prediction and positive finite reference are required")
    return 100 * (actual - reference) / reference


def paper_comparison() -> list[dict[str, Any]]:
    refs = json.loads(SOURCE.read_text())
    return [dict(paper=name, metric=row["metric"], paper_baseline=row["baseline"],
                 tool_result=None, delta=None, status="NOT_EVALUATED",
                 reason=row["blocker"], source=row["url"])
            for name, row in refs.items()]


def mohan_comparison() -> dict[str, Any]:
    """Reproduce the actual published model column, preserving measurement error."""
    from textlayout.research.formulas import spiral_inductance_nh

    path = SOURCE.with_name("mohan_1999.json")
    reference = json.loads(path.read_text())
    rows = []
    for case in reference["rows"]:
        n, outer = case["turns"], case["outer_um"]
        inner = outer - 2 * n * case["width_um"] - 2 * (n - 1) * case["spacing_um"]
        prediction = spiral_inductance_nh(n, outer, inner)
        error = -relative_error(prediction, case["measured_nh"])
        delta = error - case["published_wheeler_error_percent"]
        rows.append(dict(case, predicted_nh=prediction, recomputed_error_percent=error,
                         delta_pp=delta, model_reproduced=abs(delta) <= reference[
                             "coefficient_rounding_tolerance_pp"]))
    return dict(source=reference["url"], selection=reference["selection"], scope=reference["scope"],
                fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), total=len(rows),
                reproduced=sum(r["model_reproduced"] for r in rows),
                tolerance_pp=reference["coefficient_rounding_tolerance_pp"],
                max_model_delta_pp=max(abs(r["delta_pp"]) for r in rows),
                paper_measurement_rmse_percent=math.sqrt(sum(
                    r["published_wheeler_error_percent"]**2 for r in rows) / len(rows)),
                tool_measurement_rmse_percent=math.sqrt(sum(
                    r["recomputed_error_percent"]**2 for r in rows) / len(rows)),
                worst_measurement_ape_percent=max(abs(r["recomputed_error_percent"]) for r in rows),
                rows=rows)


def solver_comparison(output: Path) -> dict[str, Any]:
    """Fresh normal-metal FastHenry extraction on the 16 local spiral cases."""
    from textlayout import build_from_text_workflow
    from textlayout.simulation.runners import find_executable

    executable = find_executable(("fasthenry",), env_var="TEXTLAYOUT_FASTHENRY")
    rows = []
    for case in default_cases():
        if case["component"] != "SpiralInductor":
            continue
        row = dict(case, executed=False, target_pass=False, geometry_pass=False)
        try:
            if executable is None:
                raise RuntimeError("FastHenry is missing; run scripts/install_fasthenry_native.py")
            case_dir = output / case["id"]
            result = build_from_text_workflow().run(
                case["prompt"], case_dir, tolerance_percent=5.0,
                execute_solver=True, solver_executable=executable)
            extraction = json.loads((case_dir / "fasthenry_result.json").read_text())
            comparison = extraction.get("target_comparison") or {}
            row.update(geometry_pass=result.ok, extraction=extraction,
                       executed=extraction["backend_status"] == "executed",
                       target_pass=comparison.get("within_tolerance", False))
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    executable_path = Path(executable) if executable and not executable.startswith("wsl:") else None
    return dict(scope="Local normal-metal quasi-static extraction, not paper-device parity; "
                      "not a mesh-convergence study; no superconducting kinetic inductance",
                executable=executable, sha256=hashlib.sha256(executable_path.read_bytes()).hexdigest()
                if executable_path and executable_path.is_file() else None,
                total=len(rows), executed=sum(r["executed"] for r in rows),
                passed=sum(r["target_pass"] and r["geometry_pass"] and r["executed"] for r in rows),
                tolerance_percent=5.0, rows=rows)


def analytical_value(result: Any) -> tuple[float, str]:
    """An independent numerical CPW check; other families are self-consistency."""
    from scipy.special import ellipk, ellipkm1

    p = result.spec.parameters
    metadata = result.generate.geometry.metadata
    if result.intent.component == "CPW":
        k = p["center_width_um"] / (p["center_width_um"] + 2 * p["gap_um"])
        # ellipkm1(k*k) evaluates K(1-k*k) without cancellation near k=0.
        value = 30 * math.pi / math.sqrt(6.45) * float(ellipkm1(k*k) / ellipk(k*k))
        return value, "SciPy elliptic-integral check; analytical, epsilon_r=11.9"
    if result.intent.component == "IDC":
        return float(metadata["estimated_capacitance_pf"]), "Bahl model self-consistency"
    if result.intent.component == "SpiralInductor":
        return float(metadata["estimated_inductance_nh"]), "Mohan model self-consistency"
    value = 299792458 / (4 * p["length_um"] * 1e-6 * math.sqrt(6.45)) / 1e9
    return value, "quarter-wave model self-consistency"


def run_case(case: dict[str, Any], output: Path) -> dict[str, Any]:
    from textlayout import build_from_text_workflow
    from textlayout.prompt import parse_prompt

    row = dict(case, parse_ok=False, geometry_ok=False, target_ok=False,
               analytical_value=None, target_error_percent=None, error=None,
               spacing_checks=[], artifacts={}, artifact_sha256={})
    started = time.perf_counter()
    try:
        intent = parse_prompt(case["prompt"])
        row["parse_ok"] = intent.component == case["component"] and math.isclose(
            intent.target[case["target_key"]], case["target"], rel_tol=1e-12)
        if not row["parse_ok"]:
            raise ValueError("Parsed intent differs from the benchmark input")
        result = build_from_text_workflow().run(case["prompt"], output, execute_solver=False,
                                                tolerance_percent=THRESHOLD_PERCENT)
        row["verification"] = result.generate.report.to_dict()
        row["parameters"] = result.spec.parameters
        row["simulation_status"] = result.evidence.status.value
        row["spacing_checks"] = [c.to_dict() for c in result.generate.report.checks
                                 if c.name in {"geometry_min_spacing", "idc_no_comb_shorts"}]
        required = ("output.gds", "output.svg", "output.png", "layout.json",
                    "intent.json", "verification.json", "klayout_readback.json")
        row["artifacts"] = {name: str(output / name) for name in required}
        nonempty = all((output / name).is_file() and (output / name).stat().st_size > 0
                       for name in required)
        readback_ok = nonempty and json.loads(
            (output / "klayout_readback.json").read_text())["status"] == "pass"
        row["geometry_ok"] = bool(result.ok and nonempty and readback_ok)
        row["analytical_value"], row["metric_scope"] = analytical_value(result)
        row["target_error_percent"] = relative_error(row["analytical_value"], case["target"])
        row["target_ok"] = row["geometry_ok"] and abs(
            row["target_error_percent"]) <= THRESHOLD_PERCENT
        if not row["geometry_ok"]:
            row["error"] = "; ".join(result.generate.report.errors) or "Missing/invalid artifact"
        row["artifact_sha256"] = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                  for name in required if (output / name).is_file()}
    except Exception as exc:
        # Failure remains in the denominator, with a retained workflow trace if generated.
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["elapsed_s"] = time.perf_counter() - started
    row["ok"] = bool(row["parse_ok"] and row["geometry_ok"] and row["target_ok"])
    return row


def render_report(payload: dict[str, Any]) -> str:
    lines = ["# Local benchmark validation", "", "The 64-case grid checks analytical sizing "
             "and geometry without external solvers. Optional fresh FastHenry runs are "
             "reported separately below.", "",
             "| Family | Cases | Geometry pass | Target pass (0.1%) | Worst target APE (%) |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for name, summary in payload["families"].items():
        worst = summary["worst_target_ape_percent"]
        lines.append(f"| {name} | {summary['cases']} | {summary['geometry_pass']} | "
                     f"{summary['target_pass']} | {worst:.6f} |" if worst is not None else
                     f"| {name} | {summary['cases']} | {summary['geometry_pass']} | "
                     f"{summary['target_pass']} | N/A |")
    lines += ["", "## Published references (distinct devices and physics)", "",
              "| Reference | Metric | Paper baseline | Tool | Delta | Status |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in payload["literature"]:
        lines.append(f"| [{row['paper']}]({row['source']}) | {row['metric']} | "
                     f"{row['paper_baseline']} | N/A | N/A | {row['status']} |")
    lines += ["", "Fresh solver outputs on matching paper geometries are required for parity.",
              "Failed cases remain in the population. Raw prompts, results, artifact hashes, "
              "dependency versions and source hash are in results.json.", ""]
    model = payload["paper_model"]
    lines += ["## Published spiral-model reproduction", "",
              f"[Mohan Table IV]({model['source']}): {model['reproduced']}/{model['total']} "
              f"supported rows reproduce the printed modified-Wheeler error column within "
              f"{model['tolerance_pp']} percentage points (rounded coefficients/dimensions).", "",
              "| Metric, identical 29-row subset | Paper model | This implementation |",
              "| --- | ---: | ---: |",
              f"| RMS error against measurements (%) | {model['paper_measurement_rmse_percent']:.4f} "
              f"| {model['tool_measurement_rmse_percent']:.4f} |",
              f"| Maximum deviation from printed model error (pp) | 0 | {model['max_model_delta_pp']:.4f} |",
              "", f"Worst measurement APE: {model['worst_measurement_ape_percent']:.3f}%. "
              "This reproduces a published analytical model; it is not independent EM validation.", ""]
    if payload.get("fasthenry"):
        solver = payload["fasthenry"]
        lines += ["## Fresh FastHenry extraction", "",
                  f"Executed {solver['executed']}/{solver['total']} local spiral cases; "
                  f"{solver['passed']}/{solver['total']} pass geometry and the 5% inductance target.",
                  "", solver["scope"], ""]
    for row in payload["cases"]:
        if not row["ok"]:
            lines.append(f"- {row['id']}: {row['error'] or 'analytical target tolerance failed'}")
    return "\n".join(lines) + "\n"


def run_suite(output: Path, with_fasthenry: bool = False) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    # Fresh folders preserve every unchanged rerun and exclude stale success artifacts.
    run_dir = Path(tempfile.mkdtemp(prefix="run_", dir=output))
    cases = default_cases()
    manifest_bytes = json.dumps(cases, indent=2).encode()
    (run_dir / "manifest.json").write_bytes(manifest_bytes)
    results = []
    for case in cases:
        row = run_case(case, run_dir / case["id"])
        results.append(row)
        print(f"{case['id']} {case['component']}: {'PASS' if row['ok'] else 'FAIL'}", flush=True)
    families = {}
    for family in sorted({r["component"] for r in results}):
        members = [r for r in results if r["component"] == family]
        errors = [abs(r["target_error_percent"]) for r in members
                  if r["target_error_percent"] is not None]
        families[family] = dict(cases=len(members), geometry_pass=sum(r["geometry_ok"] for r in members),
                                target_pass=sum(r["target_ok"] for r in members),
                                worst_target_ape_percent=max(errors) if errors else None)
    payload = dict(schema="textlayout.local-benchmark.v1", population="local engineering grid",
                   paper_replication=False, external_solver_executed=False,
                   python=platform.python_version(), platform=platform.platform(),
                   git_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                   text=True).strip(),
                   source_diff_sha256=hashlib.sha256(subprocess.check_output(
                       ["git", "diff", "HEAD"], cwd=ROOT)).hexdigest(),
                   script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_tree_sha256=source_tree_sha256(),
                   manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                   dependencies={d.metadata["Name"]: d.version
                                 for d in importlib.metadata.distributions()},
                   total=len(results), passed=sum(r["ok"] for r in results),
                   families=families, simulation_statuses=dict(Counter(
                       r.get("simulation_status", "FAILED") for r in results)),
                   literature=paper_comparison(), paper_model=mohan_comparison(), cases=results)
    if with_fasthenry:
        payload["fasthenry"] = solver_comparison(run_dir / "fasthenry")
        payload["external_solver_executed"] = payload["fasthenry"]["executed"] > 0
    for destination in (run_dir, output):
        (destination / "results.json").write_text(json.dumps(payload, indent=2, allow_nan=False)+"\n")
        (destination / "report.md").write_text(render_report(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "audit" / "benchmark")
    parser.add_argument("--require-paper-parity", action="store_true",
                        help="Fail while exact paper-device reproduction is unavailable.")
    parser.add_argument("--with-fasthenry", action="store_true",
                        help="Also execute the 16 local spiral cases using real FastHenry")
    args = parser.parse_args()
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".tools" / "matplotlib"))
    payload = run_suite(args.out.resolve(), args.with_fasthenry)
    print(render_report(payload))
    if args.require_paper_parity:
        return 2
    if args.with_fasthenry and payload["fasthenry"]["passed"] != payload["fasthenry"]["total"]:
        return 1
    return 0 if (payload["passed"] == payload["total"] and
                 payload["paper_model"]["reproduced"] == payload["paper_model"]["total"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
