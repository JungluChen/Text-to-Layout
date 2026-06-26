"""Run fabrication-real benchmark regeneration.

This is the stable command wrapper requested by AGENTS/user workflows:

    python scripts/run_benchmarks.py

It delegates to ``scripts.generate_assets.generate_benchmarks`` so benchmark
generation uses the same strict layout, extraction, DRC, and solver-status path
as the documentation assets.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reexec_with_uv_if_needed(exc: ModuleNotFoundError) -> None:
    if os.environ.get("TEXT_TO_GDS_UV_REEXEC") == "1":
        raise exc
    env = dict(os.environ)
    env["TEXT_TO_GDS_UV_REEXEC"] = "1"
    cmd = ["py", "-3", "-m", "uv", "run", "--no-sync", "python", str(Path(__file__).resolve())]
    raise SystemExit(subprocess.call(cmd, cwd=ROOT, env=env))


def main() -> None:
    try:
        from scripts.generate_assets import ASSETS, WORKSPACE, generate_benchmarks
        from text_to_gds.device_library import CalibrationJJArray, JPA, Resonator, TWPA, Transmon
        from text_to_gds.reference_compare import compare_cpw_against_references, golden_compare
        from text_to_gds.rendering import render_layout_screenshot
        from text_to_gds.verification import generate_lvs_report
    except ModuleNotFoundError as exc:
        _reexec_with_uv_if_needed(exc)

    generate_benchmarks()
    professional_reports = []
    professional_assets = []
    for name, device in {
        "benchmark_transmon": Transmon(),
        "benchmark_flux_tunable_transmon": Transmon(frequency_ghz=5.5),
        "benchmark_JPA": JPA(),
        "benchmark_IMPA": JPA(target_gain_db=15.0),
        "benchmark_resonator": Resonator(),
        "benchmark_JJ_process_monitor": CalibrationJJArray(),
        "benchmark_readout_chain": Resonator(frequency_ghz=6.7, kind="hanger"),
        "benchmark_TWPA": TWPA(),
    }.items():
        component = device.geometry()
        gds_path = WORKSPACE / f"{name}.gds"
        png_path = WORKSPACE / f"{name}.layout.png"
        report_path = WORKSPACE / f"{name}.report.json"
        component.write_gds(gds_path)
        render_layout_screenshot(gds_path, png_path)
        lvs = generate_lvs_report(gds_path, WORKSPACE, name)
        report = {
            "schema": "text-to-gds.professional-benchmark.v1",
            "benchmark": name,
            "gds_path": str(gds_path),
            "screenshot_path": str(png_path),
            "netlist": device.netlist().to_dict(),
            "gds_derived_lvs": lvs,
            "net_overlay_path": lvs["overlay_path"],
            "equivalent_schematic_path": lvs["schematic_path"],
            "ports": {port_name: port.to_dict() for port_name, port in device.ports().items()},
            "extracted_parameters": device.extract(),
            "physics_target_comparison": component.info.get("physics_target_comparison", {}),
            "fabrication_rule_result": lvs["drc"],
            "metal_nets": component.info.get("metal_nets", {}),
            "solver_status": device.simulate(output_dir=WORKSPACE),
            "em_results": {"status": "skipped", "reason": "SKIPPED - Touchstone not produced by solver"},
            "literature_comparison": golden_compare(
                {
                    "pcell": component.info.get("device_type", name),
                    "info": dict(component.info),
                    "extraction": device.extract(),
                    "netlist": device.netlist().to_dict(),
                    "ports": {port_name: port.to_dict() for port_name, port in device.ports().items()},
                },
                "transmon" if isinstance(device, Transmon)
                else "jpa" if isinstance(device, JPA)
                else "cpw" if isinstance(device, Resonator)
                else "process" if isinstance(device, CalibrationJJArray)
                else None,
            ) if isinstance(device, (Transmon, JPA, Resonator, CalibrationJJArray)) else None,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        professional_reports.append(str(report_path))
        professional_assets.append(str(png_path))
    comparison = compare_cpw_against_references(project_root=ROOT, output_dir=WORKSPACE)
    reports = sorted(WORKSPACE.glob("benchmark_*.report.json"))
    manifest = {
        "schema": "text-to-gds.benchmark-run.v1",
        "status": "generated",
        "workspace": str(WORKSPACE),
        "reports": [str(path) for path in reports],
        "assets": [str(path) for path in sorted(ASSETS.glob("benchmark_*_*.png"))],
        "professional_reports": professional_reports,
        "professional_assets": professional_assets,
        "reference_comparison": comparison,
    }
    manifest_path = WORKSPACE / "benchmark_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
