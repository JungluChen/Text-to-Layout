"""Run physics benchmarks that require real external solver execution.

Run: uv run python scripts/run_external_benchmark.py [--benchmark N]

Without --benchmark: runs all benchmarks.
With --benchmark N:  runs only benchmark N (1–6).

Every benchmark reports PASS / FAIL with solver evidence.
A benchmark is FAIL if any required solver returned status != EXECUTED.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

WORKSPACE = ROOT / "workspace" / "benchmark_run"

from text_to_gds.design_intent import synthesize_design_intent, write_design_intent  # noqa: E402
from text_to_gds.server import compile_layout, extract_layout, run_drc, run_simulation  # noqa: E402
from text_to_gds.review.committee import review_committee  # noqa: E402

SEP = "-" * 60


def _compile(pcell: str, parameters: dict, stem: str) -> dict:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    prompt_map = {
        "manhattan_josephson_junction": "Generate a Josephson junction fabrication test structure",
        "jj_ic_calibration_array":      "Generate a JJ critical-current calibration array",
        "cpw_quarter_wave_resonator":   "Design a 6 GHz CPW quarter-wave resonator with 50 Ω impedance",
        "via_chain_monitor":            "Generate a via-chain process monitor",
        "ground_plane":                 "Generate an isolated ground-plane process coupon",
    }
    prompt = prompt_map.get(pcell, f"Generate a {pcell}")
    inputs = {"process": "benchmark", "device": pcell, **parameters}
    intent = synthesize_design_intent(prompt, inputs=inputs)
    intent_path = WORKSPACE / f"{stem}.design_intent.json"
    write_design_intent(intent, intent_path)
    return compile_layout(pcell=pcell, parameters=parameters, output_name=f"{stem}.gds")


def _report(name: str, compiled: dict, solver_status: str, solver_engine: str,
            solver_reason: str, score: int) -> dict:
    return {
        "benchmark": name,
        "gds": compiled["gds_path"],
        "solver_status": solver_status,
        "solver_engine": solver_engine,
        "solver_reason": solver_reason,
        "score": score,
        "pass": score >= 90 and solver_status == "EXECUTED",
    }


def benchmark_01_manhattan_jj() -> dict:
    """Manhattan JJ — JoSIM / JosephsonCircuits must execute."""
    print("\n[B01] Manhattan JJ (JoSIM / JosephsonCircuits.jl)")
    compiled = _compile("manhattan_josephson_junction",
                        {"junction_width": 0.22, "junction_height": 0.22}, "b01")
    sim = run_simulation(compiled["sidecar_path"],
                         simulator="JosephsonCircuits.jl", jc_ua_per_um2=2.0)
    status = "EXECUTED" if sim.get("adapter_status") == "executed" else "FAILED"
    reason = sim.get("adapter_result", {}).get("reason", "") if status != "EXECUTED" else ""
    score = 95 if status == "EXECUTED" else 40
    result = _report("B01 Manhattan JJ", compiled, status, "JosephsonCircuits.jl", reason, score)
    print(f"  Solver: {status}  Score: {score}  Pass: {result['pass']}")
    if reason:
        print(f"  Reason: {reason}")
    return result


def benchmark_02_ground_plane() -> dict:
    """Ground plane coupon — geometry + DRC only."""
    print("\n[B02] Ground plane coupon")
    compiled = _compile("ground_plane",
                        {"width": 5.0, "height": 5.0, "clearance": 1.0}, "b02")
    drc = run_drc(compiled["gds_path"], min_width_um=0.1)
    drc_ok = drc["status"] == "passed"
    score = 85 if drc_ok else 40
    result = _report("B02 Ground Plane", compiled, "SKIPPED", "none",
                     "no configured solver for ground plane", score)
    print(f"  DRC: {drc['status']}  Score: {score}")
    return result


def benchmark_03_sfq_splitter() -> dict:
    """SFQ pulse splitter — JJ device, JoSIM preferred."""
    print("\n[B03] SFQ Pulse Splitter")
    compiled = _compile("manhattan_josephson_junction",
                        {"junction_width": 0.30, "junction_height": 0.30,
                         "lead_width": 1.0, "lead_length": 4.0}, "b03")
    sim = run_simulation(compiled["sidecar_path"], simulator="josim", jc_ua_per_um2=2.0)
    status = "EXECUTED" if sim.get("adapter_status") == "executed" else "FAILED"
    reason = sim.get("adapter_result", {}).get("reason", "") if status != "EXECUTED" else ""
    score = 92 if status == "EXECUTED" else 45
    result = _report("B03 SFQ Splitter", compiled, status, "JoSIM", reason, score)
    print(f"  Solver: {status}  Score: {score}  Pass: {result['pass']}")
    return result


def benchmark_04_jj_calibration() -> dict:
    """JJ calibration array — extraction quality check."""
    print("\n[B04] JJ Calibration Array")
    compiled = _compile("jj_ic_calibration_array", {}, "b04")
    ext = extract_layout(compiled["sidecar_path"])
    has_ic = ext.get("parameters", {}).get("critical_current_ua") is not None
    score = 88 if has_ic else 50
    result = _report("B04 JJ Cal Array", compiled, "SKIPPED", "none",
                     "calibration array: extraction-only benchmark", score)
    print(f"  Ic extracted: {has_ic}  Score: {score}")
    return result


def benchmark_05_cpw_resonator() -> dict:
    """CPW resonator — openEMS or Palace must produce f0 / Z0 / .s2p."""
    print("\n[B05] CPW Quarter-Wave Resonator (openEMS)")
    compiled = _compile("cpw_quarter_wave_resonator", {}, "b05")
    from text_to_gds.server import export_openems_project
    openems = export_openems_project(compiled["sidecar_path"],
                                     output_name="b05", run=True)
    tp = openems.get("touchstone_path") or openems.get("execution", {}).get("touchstone_path")
    status = "EXECUTED" if (openems.get("status") == "executed" and tp and
                             Path(str(tp)).is_file()) else "FAILED"
    reason = (openems.get("reason") or
              "openEMS not available or did not produce a .s2p file")
    score = 95 if status == "EXECUTED" else 40
    result = _report("B05 CPW Resonator", compiled, status, "openEMS", reason, score)
    print(f"  openEMS: {status}  Score: {score}  Pass: {result['pass']}")
    return result


def benchmark_06_via_chain() -> dict:
    """Via-chain monitor — geometry + resistance estimate."""
    print("\n[B06] Via-Chain Monitor")
    compiled = _compile("via_chain_monitor", {"stage_count": 100}, "b06")
    ext = extract_layout(compiled["sidecar_path"])
    score = 80
    result = _report("B06 Via Chain", compiled, "SKIPPED", "none",
                     "no circuit solver for via chain", score)
    print(f"  Score: {score}")
    return result


BENCHMARKS = {
    1: benchmark_01_manhattan_jj,
    2: benchmark_02_ground_plane,
    3: benchmark_03_sfq_splitter,
    4: benchmark_04_jj_calibration,
    5: benchmark_05_cpw_resonator,
    6: benchmark_06_via_chain,
}


def main() -> None:
    import text_to_gds.server as _srv
    _srv.ARTIFACT_ROOT = WORKSPACE  # type: ignore[assignment]
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    selected = None
    for arg in sys.argv[1:]:
        if arg.startswith("--benchmark"):
            parts = arg.split("=")
            if len(parts) == 2:
                selected = int(parts[1])
            elif arg == "--benchmark" and sys.argv.index(arg) + 1 < len(sys.argv):
                selected = int(sys.argv[sys.argv.index(arg) + 1])

    print(SEP)
    print("Text-to-GDS — External Physics Benchmarks")
    print(SEP)

    to_run = {selected: BENCHMARKS[selected]} if selected else BENCHMARKS
    results = []
    for _n, fn in to_run.items():
        results.append(fn())

    print(f"\n{SEP}")
    passed = sum(1 for r in results if r["pass"])
    print(f"Results: {passed}/{len(results)} PASS")
    for r in results:
        verdict = "PASS" if r["pass"] else "FAIL"
        print(f"  [{verdict}] {r['benchmark']:<30} solver={r['solver_status']}")
    print(SEP)

    report_path = WORKSPACE / "benchmark_report.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull report: {report_path}")


if __name__ == "__main__":
    main()
