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
            "Inductance is a modified-Wheeler analytical estimate; FastHenry "
            "execution is optional/future. Not fabrication-ready."
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
            "Geometry-level comparison tile; sub-device numbers are analytical and "
            "no solver ran on the assembled tile. Not fabrication-ready."
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
        f"- GDS: [`output.gds`](output.gds), SVG: [`output.svg`](output.svg)",
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
        lines += [
            f"- Extracted mutual capacitance: `{simulation.get('mutual_capacitance_pf')}` pF",
        ]
    else:
        lines += ["- No solver output exists for this example; nothing electrical is claimed."]
    lines += ["", "## Target comparison", ""]
    if comparison:
        lines += [
            f"- Target: `{comparison.get('target')}`; extracted: `{comparison.get('extracted')}`",
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
