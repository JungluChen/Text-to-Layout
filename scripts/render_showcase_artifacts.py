"""Regenerate every derived showcase artifact from canonical evidence.

    uv run python scripts/render_showcase_artifacts.py [--check]

Statuses and extracted values are never written by hand. This projects
`examples/showcase/<id>/evidence/canonical.json` onto:

    simulation.json, simulation/simulation.json, openems_result.json,
    extraction/capacitance_result.json, workflow_trace.json,
    report.md, README.md, examples/showcase/index.json,
    README.md (showcase table + evidence summary)

`--check` writes nothing and exits 1 when any artifact is stale.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from textlayout.evidence.canonical import CanonicalEvidence, load_canonical  # noqa: E402
from textlayout.evidence.consistency import (  # noqa: E402
    EVIDENCE_BLOCK,
    canonical_path,
    generated_block,
    iter_showcases,
)
from textlayout.evidence.contract import EvidenceStatus  # noqa: E402
from textlayout.evidence.render import (  # noqa: E402
    evidence_block_markdown,
    render_simulation_json,
    render_solver_result_json,
    render_workflow_trace,
    replace_region,
    upsert_block,
)

_NEXT_HEADING = re.compile(r"\n## ", re.MULTILINE)


def _heading_after(text: str, heading: str) -> str:
    """The next `## ` heading following `heading`, used as an exclusive bound."""
    start = text.index(heading) + len(heading)
    match = _NEXT_HEADING.search(text, start)
    if match is None:
        raise ValueError(f"no heading follows {heading!r}")
    end = text.index("\n", match.start() + 1)
    return text[match.start() + 1 : end]


def _render_markdown(
    path: Path, record: CanonicalEvidence, start: str, after: str
) -> str:
    """Replace the whole status region so no stale prose survives beside the block.

    `after` names the last status heading; the region ends at whatever heading
    follows it, which differs per showcase (`## Limitation`, `## Region-level
    evidence`, `## Tile sub-block evidence`, ...).
    """
    text = path.read_text(encoding="utf-8")
    body = evidence_block_markdown(record)
    if generated_block(text) is not None:
        # already converted: replace the block in place, so rendering is idempotent
        inner = body.split("\n", 1)[1].rsplit("\n", 1)[0]
        return upsert_block(text, EVIDENCE_BLOCK, inner)
    end = _heading_after(text, after)  # already includes the leading "## "
    return replace_region(text, start, end, body)


def _summary_row(record: CanonicalEvidence) -> str:
    if record.extracted_value is not None:
        detail = (
            f"extracted `{record.extracted_value:.6f}` {record.extracted_unit} "
            f"versus `{record.target_value:.6f}` {record.target_unit} target; "
            f"`{record.error_percent:+.3f}%` error"
        )
    elif record.status is EvidenceStatus.SIMULATION_INVALID:
        detail = f"no value extracted — {record.invalidation_reason}"
    else:
        detail = "no solver-extracted value"
    return (
        f"| {record.design_id} | `{record.scientific_validation_level or record.status.value}` | "
        f"`{record.target_tolerance_passed}` | {record.analysis_scope} | {detail} |"
    )


def _evidence_summary(records: list[CanonicalEvidence]) -> str:
    numerically_converged = [
        r for r in records if r.scientific_validation_level == "NUMERICALLY_CONVERGED"
    ]
    executed = [r for r in records if r.status is EvidenceStatus.SIMULATION_EXECUTED]
    invalid = [r for r in records if r.status is EvidenceStatus.SIMULATION_INVALID]
    analytical = [r for r in records if r.status is EvidenceStatus.ANALYTICAL_ONLY]

    def names(group: list[CanonicalEvidence]) -> str:
        return ", ".join(f"`{r.design_id}`" for r in group) if group else "none"

    lines = [
        "",
        "<!-- Generated from examples/showcase/*/evidence/canonical.json. Do not edit. -->",
        "",
        "| Showcase | Scientific validation level | Target tolerance passed | Scope | Evidence |",
        "| --- | --- | --- | --- | --- |",
        *[_summary_row(r) for r in records],
        "",
        f"**NUMERICALLY_CONVERGED** ({len(numerically_converged)}): "
        f"{names(numerically_converged)} -- a historical solver output re-parses to the "
        "value shown, a convergence criterion was recorded, and target tolerance passed. "
        "This is not full physics signoff.",
        "",
        f"**SIMULATION_EXECUTED** ({len(executed)}): {names(executed)} — a solver ran and "
        "produced a finite value, but no convergence criterion is evidenced, so the "
        "result is not verified.",
        "",
        f"**SIMULATION_INVALID** ({len(invalid)}): {names(invalid)} — a solver ran and its "
        "output failed a physical-sanity check. No quantity was extracted.",
        "",
        f"**ANALYTICAL_ONLY** ({len(analytical)}): {names(analytical)} — no solver result "
        "for this scope.",
        "",
        "**Not claimed at all:** self-resonance, loss/Q, EM transitions, JJ physics on "
        "generic placeholders, and the fabrication readiness of anything. No example is "
        "fabrication-ready.",
        "",
    ]
    return "\n".join(lines)


def _headline_evidence(records: list[CanonicalEvidence]) -> str:
    """The quick table near the top of the README: solver-backed scopes only."""
    rows = [
        "",
        "<!-- Generated from examples/showcase/*/evidence/canonical.json. Do not edit. -->",
        "",
        "| Quantity | Target | Solver-extracted | Error | Target tolerance passed | Scientific validation level |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        if record.extracted_value is None:
            continue
        rows.append(
            f"| {record.design_id} {record.target_quantity} "
            f"| {record.target_value:.6f} {record.target_unit} "
            f"| {record.extracted_value:.6f} {record.extracted_unit} "
            f"| {abs(record.error_percent):.3f}% "
            f"| `{record.target_tolerance_passed}` "
            f"| `{record.scientific_validation_level or record.status.value}` |"
        )
    invalid = [r for r in records if r.status is EvidenceStatus.SIMULATION_INVALID]
    if invalid:
        rows += [
            "",
            "Solvers that ran but produced unusable output (no value extracted): "
            + ", ".join(f"`{r.design_id}`" for r in invalid)
            + ".",
        ]
    rows.append("")
    return "\n".join(rows)


def _verified_list(records: list[CanonicalEvidence]) -> str:
    verified = [r for r in records if r.scientific_validation_level == "NUMERICALLY_CONVERGED"]
    if not verified:
        return "\nNo showcase currently carries `NUMERICALLY_CONVERGED`.\n"
    items = ", ".join(
        f"[{r.design_id}](examples/showcase/{r.design_id}/) "
        f"({r.solver_name}, scope `{r.analysis_scope}`)"
        for r in verified
    )
    return (
        f"\nThe `NUMERICALLY_CONVERGED` artifacts are {items}. "
        "Each keeps historical solver provenance and target agreement, but missing "
        "scientific-validation gates are still recorded in canonical evidence.\n"
    )


def _verified_bullet(records: list[CanonicalEvidence]) -> str:
    verified = [
        r.design_id for r in records if r.scientific_validation_level == "NUMERICALLY_CONVERGED"
    ]
    listed = ", ".join(f"`{name}`" for name in verified) or "no showcase"
    return (
        f"\n- **NUMERICALLY_CONVERGED currently exists for {listed}.** Other scopes remain "
        "analytical, executed-without-convergence, invalid, prepared, or honestly "
        "skipped unless their canonical evidence says otherwise. No showcase carries "
        "full physics signoff.\n"
    )


def _evidence_cell(record: CanonicalEvidence) -> str:
    solver = record.solver_name or "no solver"
    if record.scientific_validation_level == "NUMERICALLY_CONVERGED":
        body = (
            f"**NUMERICALLY_CONVERGED** -- {solver} extracted {record.extracted_value:.6f} "
            f"{record.extracted_unit} versus {record.target_value:.6f} "
            f"{record.extracted_unit} target; {abs(record.error_percent):.3f}% error, "
            f"target_tolerance_passed=`{record.target_tolerance_passed}`. Convergence: "
            f"`{record.convergence.method}`. Missing gates: "
            f"{', '.join(record.missing_scientific_validation_gates) or 'none'}."
        )
    elif record.scientific_validation_level == "OUTPUT_PARSED":
        body = (
            f"**OUTPUT_PARSED** -- {solver} extracted {record.extracted_value:.6f} "
            f"{record.extracted_unit} versus {record.target_value:.6f} "
            f"{record.extracted_unit} target ({record.error_percent:+.3f}%), but no "
            f"convergence criterion is evidenced, so it is **not** physics-verified."
        )
    elif record.status is EvidenceStatus.SIMULATION_EXECUTED:
        body = (
            f"**SIMULATION_EXECUTED** — {solver} extracted {record.extracted_value:.6f} "
            f"{record.extracted_unit} versus {record.target_value:.6f} "
            f"{record.extracted_unit} target ({record.error_percent:+.3f}%), but no "
            f"convergence criterion is evidenced, so it is **not** physics-verified."
        )
    elif record.status is EvidenceStatus.SIMULATION_INVALID:
        body = (
            f"**SIMULATION_INVALID** — {solver} ran to completion, but its output failed "
            f"a physical-sanity check: {record.invalidation_reason} No value was extracted."
        )
    else:
        body = f"**{record.status.value}** for scope `{record.analysis_scope}`."
    return f"{body} **NOT_FABRICATION_READY**"


def _showcase_table(records: list[CanonicalEvidence], index: dict[str, object]) -> str:
    entries = {e["id"]: e for e in index["examples"]}  # type: ignore[index,union-attr]
    lines = [
        "",
        "<!-- Generated from examples/showcase/*/evidence/canonical.json. Do not edit. -->",
        "",
        "| # | Target | Prompt | Output | Step Results | Evidence Status |",
        "|---|--------|--------|--------|--------------|-----------------|",
    ]
    for number, record in enumerate(records, start=1):
        entry = entries[record.design_id]
        directory = f"examples/showcase/{record.design_id}"
        image = f"[![{record.component}]({directory}/output.png)]({directory}/output.svg)"
        links = (
            f"[report]({directory}/report.md) · "
            f"[simulation]({directory}/simulation.json) · "
            f"[trace]({directory}/workflow_trace.json) · "
            f"[evidence]({directory}/evidence/canonical.json)"
        )
        lines.append(
            f"| {number} | {entry['target']} | {entry['prompt']} | {image} | {links} "
            f"| {_evidence_cell(record)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _index_entry(entry: dict[str, object], record: CanonicalEvidence) -> dict[str, object]:
    display_status = record.scientific_validation_level or record.status.value
    entry["evidence_status"] = display_status
    entry["simulation_status"] = display_status
    entry["solver_execution_status"] = record.status.value
    entry["scientific_validation_level"] = record.scientific_validation_level or record.status.value
    entry["target_tolerance_passed"] = record.target_tolerance_passed
    entry["solver"] = record.solver_name or "none"
    entry["solver_executed"] = record.solver_name is not None and record.status not in {
        EvidenceStatus.ANALYTICAL_ONLY,
        EvidenceStatus.SKIPPED_SOLVER_ABSENT,
    }
    entry["canonical_evidence_id"] = record.evidence_id
    if record.status is EvidenceStatus.SIMULATION_INVALID:
        entry["limitation"] = (
            f"{record.solver_name} ran to completion, but its output failed a "
            f"physical-sanity check: {record.invalidation_reason} No quantity was "
            "extracted. Not fabrication-ready."
        )
    elif record.status is EvidenceStatus.SIMULATION_EXECUTED and record.convergence is not None:
        entry["limitation"] = (
            f"{record.solver_name} extracted {record.extracted_value:.6f} "
            f"{record.extracted_unit} versus a {record.target_value:.6f} "
            f"{record.target_unit} target, but no convergence criterion is evidenced "
            f"({record.convergence.method}), so the result is not physics-verified. "
            "Not fabrication-ready."
        )
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    showcases = iter_showcases(ROOT)
    records = [load_canonical(canonical_path(s)) for s in showcases]
    stale: list[str] = []

    def emit(path: Path, new_text: str) -> None:
        old = path.read_text(encoding="utf-8") if path.is_file() else None
        if old == new_text:
            return
        if args.check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(new_text, encoding="utf-8")

    def emit_json(path: Path, mutate) -> None:  # type: ignore[no-untyped-def]
        if not path.is_file():
            return
        before = path.read_text(encoding="utf-8")
        mutate()
        after = path.read_text(encoding="utf-8")
        if before != after and args.check:
            path.write_text(before, encoding="utf-8")
            stale.append(str(path.relative_to(ROOT)))

    for showcase, record in zip(showcases, records, strict=True):
        emit_json(showcase / "simulation.json",
                  lambda s=showcase, r=record: render_simulation_json(r, s / "simulation.json"))
        emit_json(
            showcase / "simulation" / "simulation.json",
            lambda s=showcase, r=record: render_simulation_json(
                r, s / "simulation" / "simulation.json"
            ),
        )
        for name in ("openems_result.json", "extraction/capacitance_result.json"):
            emit_json(
                showcase / name,
                lambda s=showcase, r=record, n=name: render_solver_result_json(r, s / n),
            )
        emit_json(
            showcase / "workflow_trace.json",
            lambda s=showcase, r=record: render_workflow_trace(r, s / "workflow_trace.json"),
        )

        for markdown, start, after in (
            ("report.md", "## Extraction status", "## Extraction status"),
            ("README.md", "## Solver execution", "## Evidence status"),
        ):
            path = showcase / markdown
            if path.is_file():
                emit(path, _render_markdown(path, record, start, after))

    # examples/showcase/index.json
    index_path = ROOT / "examples" / "showcase" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    by_id = {r.design_id: r for r in records}
    for entry in index["examples"]:
        if entry["id"] in by_id:
            _index_entry(entry, by_id[entry["id"]])
    emit(index_path, json.dumps(index, indent=2) + "\n")

    # top-level README: showcase table + evidence summary
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    readme = upsert_block(readme, "showcase-table", _showcase_table(records, index))
    readme = upsert_block(readme, "evidence-summary", _evidence_summary(records))
    readme = upsert_block(readme, "headline-evidence", _headline_evidence(records))
    readme = upsert_block(readme, "verified-list", _verified_list(records))
    readme = upsert_block(readme, "verified-bullet", _verified_bullet(records))
    emit(readme_path, readme)

    if args.check:
        for path in stale:
            print(f"::error::stale derived artifact: {path}")
        if stale:
            print(
                f"\n{len(stale)} artifact(s) disagree with canonical evidence. "
                "Run scripts/render_showcase_artifacts.py and commit."
            )
            return 1
        print("all derived showcase artifacts are current.")
    else:
        print(f"rendered {len(showcases)} showcases from canonical evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
