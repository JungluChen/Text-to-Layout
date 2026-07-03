"""Generate the six committed research-grade showcase examples.

Deterministic and re-runnable::

    uv run python scripts/generate_showcase_examples.py --force

Each example runs the full LangGraph pipeline (parse → DSL → geometry →
KLayout readback → solver preparation → guarded FasterCap execution → evidence
report) and leaves a complete artifact chain under ``examples/showcase/<id>/``.
Existing example folders are not overwritten unless ``--force`` is passed.

The script never invents solver results: on a machine without FasterCap the
IDC examples honestly record ``SKIPPED_SOLVER_ABSENT`` and the committed
artifacts say so.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SHOWCASE_DIR = ROOT / "examples" / "showcase"

REQUIRED_FILES = (
    "prompt.txt",
    "intent.json",
    "layout.json",
    "output.gds",
    "output.svg",
    "output.png",
    "verification.json",
    "klayout_readback.json",
    "simulation.json",
    "optimization.json",
    "workflow_trace.json",
    "report.md",
    "README.md",
)


@dataclass(frozen=True)
class Example:
    id: str
    title: str
    target: str
    prompt: str
    limitation: str


EXAMPLES: tuple[Example, ...] = (
    Example(
        id="01_idc_0p6pf",
        title="IDC capacitor, 0.6 pF",
        target="0.6 pF interdigitated capacitor for a lumped LC / JPA front end",
        prompt=(
            "Create a 0.6 pF interdigitated capacitor on silicon at 6 GHz with "
            "2 um minimum gap, 4 um finger width, and two RF ports."
        ),
        limitation=(
            "Effective-medium electrostatic model; no self-resonance, loss, or "
            "finite-thickness model. Not fabrication-ready."
        ),
    ),
    Example(
        id="02_cpw_50ohm",
        title="50 ohm CPW feedline",
        target="50 ohm coplanar-waveguide feedline for microwave routing",
        prompt=(
            "Create a 50 ohm CPW feedline on silicon at 6 GHz with "
            "ground-signal-ground geometry and labeled input/output ports."
        ),
        limitation=(
            "Impedance is a conformal-mapping analytical estimate; no EM solver "
            "was executed. Not fabrication-ready."
        ),
    ),
    Example(
        id="03_idc_cpw_test_structure",
        title="IDC + CPW test structure",
        target="0.6 pF IDC with CPW launches for on-chip measurement",
        prompt=(
            "Create a test structure with a 0.6 pF IDC connected to two 50 ohm "
            "CPW feedlines, with GSG-style launch regions, ground clearance, "
            "and measurement-friendly port labels."
        ),
        limitation=(
            "Only the embedded IDC region is extracted; launches, feeds, and "
            "transitions are not simulated. Not fabrication-ready."
        ),
    ),
    Example(
        id="04_spiral_inductor_3nh",
        title="Spiral inductor, 3 nH",
        target="Compact planar spiral inductor targeting 3 nH",
        prompt=(
            "Create a compact planar spiral inductor targeting 3 nH with 4 turns, "
            "4 um trace width, 2 um spacing, and two labeled ports."
        ),
        limitation=(
            "FastHenry execution is environment-dependent; conductivity and "
            "thickness remain generic process assumptions. Not fabrication-ready."
        ),
    ),
    Example(
        id="05_quarter_wave_resonator_6ghz",
        title="Quarter-wave CPW resonator, 6 GHz",
        target="6 GHz quarter-wave CPW resonator layout candidate",
        prompt=(
            "Create a 6 GHz quarter-wave resonator on silicon with a weakly "
            "coupled input line, open end, shorted end, and port labels."
        ),
        limitation=(
            "Length uses the analytical lambda/4 estimate with effective "
            "permittivity; no EM eigenmode verification. Not fabrication-ready."
        ),
    ),
    Example(
        id="06_research_test_chip",
        title="Research test-chip tile, 2 mm x 2 mm",
        target="Multi-device comparison tile (IDC + CPW + spiral + marks + title)",
        prompt=(
            "Create a 2 mm by 2 mm research test chip tile containing a 0.6 pF IDC, "
            "a 50 ohm CPW line, a spiral inductor, alignment marks, port labels, "
            "and a title text label."
        ),
        limitation=(
            "No full-tile solver ran. The tile map records exact-parameter sub-block "
            "execution or preparation without promoting it to tile verification. "
            "Not fabrication-ready."
        ),
    ),
)


def _relocate(out: Path, result_files: dict[str, str]) -> None:
    """Nothing to move today — the pipeline already writes canonical names."""


def _canonicalize_gds(out: Path, cell_name: str) -> None:
    from textlayout.exporters.gds_exporter import canonicalize_gds

    gds = out / "output.gds"
    if gds.is_file():
        canonicalize_gds(gds, cell_name=cell_name)


def _wsl_path(path: Path) -> str | None:
    """Return the conventional WSL mount path for a Windows path."""
    drive = path.drive.rstrip(":")
    if not drive:
        return None
    tail = path.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive.lower()}/{tail}"


def _sanitize_committed_paths(out: Path) -> None:
    """Remove machine-specific checkout prefixes from committed text artifacts.

    Runtime objects retain absolute paths while the workflow is executing. The
    showcase is a portable release packet, so paths persisted under it are
    rewritten relative to either the example directory or repository root.
    """
    replacements: list[tuple[str, str]] = []
    for base, replacement in ((out, ""), (ROOT, "")):
        variants = {str(base), base.as_posix()}
        wsl = _wsl_path(base)
        if wsl:
            variants.add(wsl)
        for variant in variants:
            for separator in ("/", "\\"):
                prefix = variant.rstrip("/\\") + separator
                replacements.append((prefix, replacement))
                replacements.append((prefix.replace("\\", "\\\\"), replacement))
    replacements.sort(key=lambda item: len(item[0]), reverse=True)

    for path in out.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        sanitized = text
        for prefix, replacement in replacements:
            sanitized = sanitized.replace(prefix, replacement)
        if sanitized != text:
            path.write_text(sanitized, encoding="utf-8")


def _write_tile_simulation_map(out: Path) -> None:
    """Run or prepare exact-parameter TestChip sub-block simulations."""
    from textlayout import build_default_workflow
    from textlayout.schemas.dsl import LayoutSpec
    from textlayout.schemas.dsl.test_chip import TestChipSpec
    from textlayout.simulation import simulate_layout

    layout = json.loads((out / "layout.json").read_text(encoding="utf-8"))
    params = TestChipSpec.model_validate(layout.get("parameters", {}))
    specs = (
        (
            "IDC",
            LayoutSpec(
                component="IDC",
                target={"capacitance_pf": layout.get("target", {}).get("capacitance_pf", 0.6)},
                parameters={
                    "finger_pairs": params.idc_finger_pairs,
                    "finger_width_um": params.idc_finger_width_um,
                    "gap_um": params.idc_gap_um,
                    "overlap_um": params.idc_overlap_um,
                    "bus_width_um": params.idc_bus_width_um,
                    "metal_layer": params.metal_layer,
                },
            ),
            "FasterCap extraction of the geometry-identical IDC sub-block",
        ),
        (
            "CPW",
            LayoutSpec(
                component="CPW",
                target={"impedance_ohm": layout.get("target", {}).get("impedance_ohm", 50.0)},
                parameters={
                    "center_width_um": params.cpw_center_width_um,
                    "gap_um": params.cpw_gap_um,
                    "ground_width_um": params.cpw_ground_width_um,
                    "length_um": params.cpw_length_um,
                    "metal": params.metal_layer,
                },
            ),
            "openEMS preparation for the geometry-identical CPW sub-block",
        ),
        (
            "SpiralInductor",
            LayoutSpec(
                component="SpiralInductor",
                target={},
                parameters={
                    "turns": params.spiral_turns,
                    "outer_dimension_um": params.spiral_outer_dimension_um,
                    "trace_width_um": params.spiral_trace_width_um,
                    "spacing_um": params.spiral_spacing_um,
                    "metal": params.metal_layer,
                },
            ),
            "FastHenry extraction of the geometry-identical spiral sub-block; no tile prompt target",
        ),
        (
            "Resonator",
            LayoutSpec(
                component="QuarterWaveResonator",
                target={"frequency_ghz": 6.0},
                parameters={
                    "center_width_um": params.cpw_center_width_um,
                    "gap_um": params.cpw_gap_um,
                    "length_um": 4800.0,
                    "coupling_gap_um": 4.0,
                    "metal": params.metal_layer,
                },
            ),
            "Nominal 6 GHz resonator reference sub-block; not embedded in the current tile geometry",
        ),
    )
    workflow = build_default_workflow()
    subblocks: dict[str, object] = {}
    for name, spec, scope in specs:
        built = workflow.run(spec, formats=())
        subdir = out / "tile_subblocks" / name.lower()
        result = simulate_layout(
            spec,
            built.geometry,
            workflow.technology(spec.technology),
            subdir,
            execute=True,
            tolerance_pct=5.0,
        )
        result_path = subdir / "simulation_result.json"
        result_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        status = (
            "PHYSICS_VERIFIED"
            if result.physics_verified
            else "SIMULATION_EXECUTED"
            if result.solver_executed
            else "SKIPPED_SOLVER_ABSENT"
            if result.status == "skipped"
            else "SIMULATION_INPUT_PREPARED"
            if result.status == "input_files_prepared"
            else "FAILED"
        )
        subblocks[name] = {
            "scope": scope,
            "status": status,
            "solver": result.solver,
            "solver_executed": result.solver_executed,
            "physics_verified": result.physics_verified,
            "extracted_quantities": result.extracted_quantities,
            "target_comparison": result.target_comparison,
            "result": str(result_path),
            "limitation": scope,
        }
    subblocks["AlignmentMarksAndLabels"] = {
        "scope": "Alignment marks and title labels in the assembled tile",
        "status": "GEOMETRY_ONLY",
        "solver": "none",
        "solver_executed": False,
        "physics_verified": False,
        "extracted_quantities": {},
        "target_comparison": None,
        "limitation": "Non-electrical geometry; no solver model applies.",
    }
    payload = {
        "schema": "textlayout.tile-simulation-map.v1",
        "full_tile_solver_executed": False,
        "full_tile_status": "NOT_MODELED",
        "fabrication_status": "NOT_FABRICATION_READY",
        "statement": (
            "This is a layout integration candidate with sub-block evidence, not a "
            "full-chip EM-verified design. Inter-block coupling, package, transitions, "
            "and whole-tile modes are not modeled."
        ),
        "subblocks": subblocks,
    }
    (out / "tile_simulation_map.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def _write_region_evidence_map(out: Path) -> None:
    """Record separate IDC, CPW-feed, and transition evidence for Example 3."""
    from textlayout import build_default_workflow
    from textlayout.schemas.dsl import LayoutSpec
    from textlayout.schemas.dsl.test_structure import TestStructureSpec
    from textlayout.simulation import simulate_layout

    layout = json.loads((out / "layout.json").read_text(encoding="utf-8"))
    params = TestStructureSpec.model_validate(layout.get("parameters", {}))
    standalone = json.loads((out / "simulation.json").read_text(encoding="utf-8"))
    idc_evidence = (standalone.get("evidence") or [{}])[0]
    comparison = standalone.get("target_comparison") or {}

    cpw_spec = LayoutSpec(
        component="CPW",
        target={"impedance_ohm": layout.get("target", {}).get("impedance_ohm", 50.0)},
        parameters={
            "center_width_um": params.feed_width_um,
            "gap_um": params.feed_gap_um,
            "ground_width_um": params.ground_width_um,
            "length_um": 2.0 * params.feed_length_um,
            "metal": params.metal_layer,
        },
    )
    workflow = build_default_workflow()
    generated = workflow.run(cpw_spec, formats=())
    cpw_dir = out / "region_simulations" / "cpw_launch_and_feed"
    cpw_result = simulate_layout(
        cpw_spec,
        generated.geometry,
        workflow.technology(cpw_spec.technology),
        cpw_dir,
        execute=True,
        tolerance_pct=10.0,
    )
    cpw_result_path = cpw_dir / "simulation_result.json"
    cpw_result_path.write_text(json.dumps(cpw_result.to_dict(), indent=2) + "\n", encoding="utf-8")
    cpw_status = (
        "PHYSICS_VERIFIED"
        if cpw_result.physics_verified
        else "SIMULATION_EXECUTED"
        if cpw_result.solver_executed
        else "SKIPPED_SOLVER_ABSENT"
        if cpw_result.status == "skipped"
        else "SIMULATION_INPUT_PREPARED"
        if cpw_result.status == "input_files_prepared"
        else "FAILED"
    )
    payload = {
        "schema": "textlayout.region-evidence-map.v1",
        "regions": [
            {
                "name": "embedded_idc",
                "solver": idc_evidence.get("solver", standalone.get("solver")),
                "status": idc_evidence.get("status"),
                "target": f"{idc_evidence.get('target_value')} {idc_evidence.get('target_unit')}",
                "extracted": f"{idc_evidence.get('extracted_value')} {idc_evidence.get('extracted_unit')}",
                "error_pct": comparison.get("error_pct"),
                "limitation": "FasterCap verification applies only to the embedded IDC extraction region.",
            },
            {
                "name": "cpw_launch_and_feed",
                "solver": cpw_result.solver,
                "status": cpw_status,
                "extracted_quantities": cpw_result.extracted_quantities,
                "target_comparison": cpw_result.target_comparison,
                "reason": cpw_result.reason,
                "result": str(cpw_result_path),
                "limitation": "Standalone feed model; it excludes launch pads and the IDC transition.",
            },
            {
                "name": "transition_region",
                "solver": "not modeled",
                "status": "NOT_MODELED",
                "limitation": "No full-wave transition model was executed.",
            },
        ],
        "whole_structure_solver_executed": False,
        "whole_structure_verified": False,
        "statement": (
            "FasterCap verification applies only to the embedded IDC extraction region. "
            "CPW launches, feedlines, and transitions are not full-wave verified unless "
            "a whole-structure openEMS execution is available."
        ),
    }
    (out / "region_evidence_map.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def _append_region_summary_to_report(out: Path) -> None:
    path = out / "region_evidence_map.json"
    report = out / "report.md"
    if not path.is_file() or not report.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    lines = ["## Region-level evidence", "", f"- {payload['statement']}"]
    for region in payload["regions"]:
        lines.append(
            f"- **{region['name']}**: `{region['status']}` via `{region['solver']}`; "
            f"{region.get('limitation', region.get('reason', ''))}"
        )
    lines += ["", "- Whole structure verified: **false**", ""]
    text = report.read_text(encoding="utf-8")
    marker = "## Limitations"
    summary = "\n".join(lines)
    text = text.replace(marker, summary + "\n" + marker, 1) if marker in text else text + summary
    report.write_text(text, encoding="utf-8")


def _tile_summary_lines(tile_map: dict[str, object]) -> list[str]:
    """Render a human-readable summary of ``tile_simulation_map.json``.

    Never claims a full-tile solve; only restates the sub-block evidence that
    is actually recorded (or its absence) for each sub-device.
    """
    lines = [
        "## Tile sub-block evidence",
        "",
        f"- Full-tile solver executed: **{tile_map.get('full_tile_solver_executed')}**",
        f"- Full-tile status: **{tile_map.get('full_tile_status')}**",
        f"- {tile_map.get('statement', '')}".rstrip(),
        "",
    ]
    subblocks = tile_map.get("subblocks")
    if isinstance(subblocks, dict):
        for name, info in subblocks.items():
            if not isinstance(info, dict):
                continue
            solver = info.get("solver") or "no solver"
            status = info.get("status", "UNKNOWN")
            scope = info.get("scope", "")
            line = f"- **{name}** sub-block: `{status}` via `{solver}` — {scope}"
            comparison = info.get("target_comparison")
            if isinstance(comparison, dict):
                line += (
                    f"; extracted `{comparison.get('extracted')}` vs target "
                    f"`{comparison.get('target')}` ({comparison.get('quantity')}); "
                    f"error `{comparison.get('error_pct')}%` "
                    f"(tolerance `{comparison.get('tolerance_pct')}%`); "
                    f"within tolerance: **{comparison.get('within_tolerance')}**"
                )
            lines.append(line)
    lines += [
        "",
        "Full-tile EM solve status: **NOT EXECUTED**. Sub-block evidence above is "
        "not a full-tile verification; alignment marks, title, inter-block "
        "coupling, package, transitions, and whole-tile modes are not modeled.",
        "",
    ]
    return lines


def _append_tile_summary_to_report(out: Path) -> None:
    """Append the tile sub-block evidence summary to the committed report.md."""
    tile_map_path = out / "tile_simulation_map.json"
    report_path = out / "report.md"
    if not tile_map_path.is_file() or not report_path.is_file():
        return
    tile_map = json.loads(tile_map_path.read_text(encoding="utf-8"))
    summary = "\n".join(_tile_summary_lines(tile_map))
    report_text = report_path.read_text(encoding="utf-8")
    marker = "## Limitations"
    if marker in report_text:
        report_text = report_text.replace(marker, summary + "\n" + marker, 1)
    else:
        report_text = report_text.rstrip() + "\n\n" + summary
    report_path.write_text(report_text, encoding="utf-8")


def _example_readme(example: Example, out: Path) -> str:
    intent = json.loads((out / "intent.json").read_text(encoding="utf-8"))
    layout = json.loads((out / "layout.json").read_text(encoding="utf-8"))
    verification = json.loads((out / "verification.json").read_text(encoding="utf-8"))
    readback = json.loads((out / "klayout_readback.json").read_text(encoding="utf-8"))
    simulation = json.loads((out / "simulation.json").read_text(encoding="utf-8"))

    evidence = (simulation.get("evidence") or [{}])[0]
    status = evidence.get("status", simulation.get("status", "UNKNOWN"))
    solver_executed = bool(simulation.get("solver_executed"))
    comparison = simulation.get("target_comparison")
    checks = verification.get("checks", [])
    passed_checks = sum(1 for c in checks if c.get("status") == "pass")

    lines = [
        f"# {example.title}",
        "",
        f"**Target.** {example.target}",
        "",
        "## Prompt",
        "",
        "```text",
        example.prompt,
        "```",
        "",
        "## Parsed intent",
        "",
        f"- Component: `{intent.get('component')}`",
        f"- Technology: `{intent.get('technology')}`",
        f"- Targets: `{json.dumps(intent.get('target', {}))}`",
        f"- Constraints: `{json.dumps(intent.get('constraints', {}))}`",
        "",
        "## Layout DSL summary",
        "",
        f"- DSL component: `{layout.get('component')}` (schema v{layout.get('dsl_version')})",
        f"- Parameters: `{json.dumps(layout.get('parameters', {}))}`",
        "",
        "## Generated geometry",
        "",
        "![layout](output.png)",
        "",
        "- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)",
        "",
        "## KLayout readback",
        "",
        f"- Status: **{readback.get('status', 'unknown').upper()}**",
        f"- Top cell: `{readback.get('top_cell')}`",
        f"- Bounding box: `{json.dumps(readback.get('bbox_um'))}` um",
        f"- Layers (GDS layer/datatype -> polygons): `{json.dumps(readback.get('layers'))}`",
        f"- Database unit: `{readback.get('dbu_um')}` um",
        "",
        "## Verification result",
        "",
        f"- Verification: **{verification.get('status', 'unknown').upper()}** "
        f"({passed_checks}/{len(checks)} checks passed)",
        "",
        "## Simulation preparation",
        "",
        f"- Solver: `{simulation.get('solver')}`",
        f"- Prepared input artifacts: `{json.dumps(sorted(simulation.get('artifacts', {})))}`",
        "",
        "## Solver execution",
        "",
        f"- Solver executed: **{'yes' if solver_executed else 'no'}**",
    ]
    if solver_executed:
        extracted = evidence.get("extracted_value")
        unit = evidence.get("extracted_unit") or ""
        lines += [
            f"- Extracted {evidence.get('quantity', 'quantity')}: `{extracted}` {unit}",
        ]
    else:
        lines += ["- No solver output exists for this example; nothing electrical is claimed."]
    lines += ["", "## Target comparison", ""]
    if comparison:
        display_target = evidence.get("target_value", comparison.get("target"))
        display_extracted = evidence.get("extracted_value", comparison.get("extracted"))
        display_unit = evidence.get("target_unit") or evidence.get("extracted_unit") or ""
        lines += [
            f"- Target: `{display_target}` {display_unit}; "
            f"extracted: `{display_extracted}` {display_unit}",
            f"- Error: `{comparison.get('error_pct')}%` "
            f"(tolerance `{comparison.get('tolerance_pct')}%`)",
            f"- Within tolerance: **{comparison.get('within_tolerance')}**",
        ]
    else:
        lines += ["- No solver-backed target comparison exists (see evidence status)."]
    lines += [
        "",
        "## Evidence status",
        "",
        f"- **{status}**",
        f"- Geometry: **{'GEOMETRY_PASS' if verification.get('status') == 'pass' and readback.get('status') == 'pass' else 'FAILED'}**",
        "- Fabrication status: **NOT_FABRICATION_READY**",
        "",
    ]
    tile_map_path = out / "tile_simulation_map.json"
    if tile_map_path.is_file():
        tile_map = json.loads(tile_map_path.read_text(encoding="utf-8"))
        lines += _tile_summary_lines(tile_map)
    region_map_path = out / "region_evidence_map.json"
    if region_map_path.is_file():
        region_map = json.loads(region_map_path.read_text(encoding="utf-8"))
        lines += ["## Region-level evidence", "", f"- {region_map.get('statement')}"]
        for region in region_map.get("regions", []):
            lines.append(
                f"- **{region.get('name')}**: `{region.get('status')}` via "
                f"`{region.get('solver')}`; {region.get('limitation', region.get('reason', ''))}"
            )
        lines += ["", "- Whole structure verified: **false**", ""]
    lines += [
        "## Limitation",
        "",
        f"{example.limitation}",
        "",
        "## Files",
        "",
    ]
    for name in REQUIRED_FILES:
        if (out / name).is_file():
            lines.append(f"- [`{name}`]({name})")
    if (out / "tile_simulation_map.json").is_file():
        lines.append("- [`tile_simulation_map.json`](tile_simulation_map.json) — sub-block scope map")
    lines += [
        "- [`extraction/`](extraction/) — solver inputs and solver-owned outputs (when executed)",
        "",
        "Regenerate with: "
        "`uv run python scripts/generate_showcase_examples.py --force`",
    ]
    return "\n".join(lines) + "\n"


def generate_example(example: Example, *, force: bool) -> dict[str, object]:
    from textlayout import build_from_text_workflow

    out = SHOWCASE_DIR / example.id
    if out.exists():
        if not force:
            print(f"[skip] {example.id}: exists (use --force to regenerate)")
            index_entry = _index_entry(example, out)
            return index_entry
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "prompt.txt").write_text(example.prompt + "\n", encoding="utf-8")

    workflow = build_from_text_workflow()
    result = workflow.run(example.prompt, out, tolerance_percent=5.0, execute_solver=True)
    _canonicalize_gds(out, example.id)
    if example.id == "03_idc_cpw_test_structure":
        _write_region_evidence_map(out)
        _append_region_summary_to_report(out)
    if example.id == "06_research_test_chip":
        _write_tile_simulation_map(out)
        _append_tile_summary_to_report(out)
    (out / "README.md").write_text(_example_readme(example, out), encoding="utf-8")
    _sanitize_committed_paths(out)

    missing = [name for name in REQUIRED_FILES if not (out / name).is_file()]
    if missing:
        raise SystemExit(f"{example.id}: missing required artifacts: {missing}")
    print(
        f"[ok]   {example.id}: geometry={result.generate.report.status} "
        f"evidence={result.evidence.status.value}"
    )
    return _index_entry(example, out)


def _index_entry(example: Example, out: Path) -> dict[str, object]:
    simulation = json.loads((out / "simulation.json").read_text(encoding="utf-8"))
    verification = json.loads((out / "verification.json").read_text(encoding="utf-8"))
    readback = json.loads((out / "klayout_readback.json").read_text(encoding="utf-8"))
    evidence = (simulation.get("evidence") or [{}])[0]
    geometry_ok = verification.get("status") == "pass" and readback.get("status") == "pass"
    return {
        "id": example.id,
        "target": example.target,
        "prompt": example.prompt,
        "artifact_dir": f"examples/showcase/{example.id}",
        "geometry_status": "GEOMETRY_PASS" if geometry_ok else "FAILED",
        "klayout_readback_status": readback.get("status", "unknown"),
        "solver": simulation.get("solver"),
        "solver_executed": bool(simulation.get("solver_executed")),
        "simulation_status": evidence.get("status", "UNKNOWN"),
        "evidence_status": evidence.get("status", "UNKNOWN"),
        "fabrication_status": "NOT_FABRICATION_READY",
        "limitation": example.limitation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Regenerate existing examples.")
    parser.add_argument("--only", default=None, help="Generate a single example id.")
    args = parser.parse_args(argv)

    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for example in EXAMPLES:
        if args.only and example.id != args.only:
            continue
        entries.append(generate_example(example, force=args.force))
    if not args.only:
        index_path = SHOWCASE_DIR / "index.json"
        index_path.write_text(
            json.dumps({"schema": "textlayout.showcase-index.v1", "examples": entries}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(f"[ok]   index written: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
