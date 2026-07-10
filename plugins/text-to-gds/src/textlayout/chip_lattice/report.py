"""Render chip-level collision/yield results to JSON, Markdown, and CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from textlayout.chip_lattice.models import ChipOptimizeResult, ChipYieldResult


def chip_report_provenance() -> dict[str, object]:
    """The status/PDK block every chip-level report must carry.

    Chip collision yield here is a statistical model over target frequencies
    and process sigmas — never a measured or field-solved result, and never
    fabrication-ready. The PDK record says which (illustrative) process file
    backed the assumptions.
    """
    from textlayout.epr.pdk_bridge import DEFAULT_PDK_NAME, resolve_pdk_path
    from textlayout.pdk.provenance import describe_pdk_file

    return {
        "status": "SYNTHETIC_EXAMPLE",
        "evidence_class": "ANALYTICAL_ONLY",
        "fabrication_readiness": "NOT_FABRICATION_READY",
        "pdk_provenance": describe_pdk_file(resolve_pdk_path(DEFAULT_PDK_NAME)).model_dump(
            mode="json"
        ),
        "note": (
            "Monte Carlo over analytical frequency-collision rules with "
            "illustrative process sigmas; no solver, no measured hardware. "
            "Collision pairs are undirected (node_a/node_b order carries no "
            "meaning)."
        ),
    }


_PROVENANCE_MD = (
    "## Provenance / honesty\n"
    "\n"
    "- **Status:** SYNTHETIC_EXAMPLE / ANALYTICAL_ONLY — statistical model, "
    "no solver, no measured hardware.\n"
    "- **Fabrication readiness:** NOT_FABRICATION_READY.\n"
    "- Collision pairs are undirected; node_a/node_b order carries no meaning.\n"
)


def write_chip_yield_report(
    result: ChipYieldResult,
    out_dir: str | Path,
    *,
    provenance: dict[str, object] | None = None,
) -> dict[str, str]:
    """Write ``chip_yield_report.{json,md}`` and ``collision_matrix.csv``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "chip_yield_report.json"
    md_path = out / "chip_yield_report.md"
    csv_path = out / "collision_matrix.csv"
    payload = result.to_dict()
    payload["provenance"] = provenance or chip_report_provenance()
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(result) + "\n" + _PROVENANCE_MD, encoding="utf-8")
    _write_collision_csv(result, csv_path)
    return {"json": str(json_path), "markdown": str(md_path), "collision_matrix": str(csv_path)}


def _write_collision_csv(result: ChipYieldResult, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["node_a", "node_b", "rule", "collision_probability"])
        for pair in result.risky_pairs:
            writer.writerow(
                [pair.node_a, pair.node_b, pair.rule, f"{pair.collision_probability:.6f}"]
            )
        if not result.risky_pairs:
            writer.writerow(["(none)", "(none)", "(no violations observed)", "0.000000"])


def render_markdown(result: ChipYieldResult) -> str:
    lines: list[str] = [
        f"# Chip collision-yield report — {result.lattice_name}",
        "",
        f"- **Nodes:** {result.nominal_report.n_nodes}",
        f"- **Samples:** {result.n_samples}",
        f"- **Seed:** {result.seed} (rerun with the same seed for identical output)",
        f"- **Nominal (target-frequency) collision-free:** "
        f"{'YES' if result.nominal_report.collision_free else 'NO'} "
        f"({result.nominal_report.n_violations} violation(s) at nominal frequencies)",
        "",
        "## Monte Carlo collision-free yield",
        "",
        f"- **{result.collision_free_pct:.4f}%** of simulated chips are fully "
        f"collision-free (95% CI: {result.collision_free_ci95_pct[0]:.4f}"
        f"–{result.collision_free_ci95_pct[1]:.4f}%)",
        "",
    ]
    if result.risky_pairs:
        lines += [
            "## Top risky pairs",
            "",
            "| Node A | Node B | Rule | Collision probability |",
            "| --- | --- | --- | --- |",
        ]
        for pair in result.risky_pairs[:20]:
            lines.append(
                f"| {pair.node_a} | {pair.node_b} | {pair.rule} | "
                f"{pair.collision_probability:.2%} |"
            )
        lines.append("")
    else:
        lines += ["No collisions observed in any Monte Carlo sample.", ""]
    lines += ["## Assumptions", ""]
    lines += [f"- {a}" for a in result.assumptions]
    lines.append("")
    return "\n".join(lines)


def render_optimize_markdown(result: ChipOptimizeResult) -> str:
    lines: list[str] = [
        f"# Chip frequency-retune report — {result.lattice_name}",
        "",
        f"- **Before:** {result.before.n_violations} violation(s), "
        f"collision_free={result.before.collision_free}",
        f"- **After:** {result.after.n_violations} violation(s), "
        f"collision_free={result.after.collision_free}",
        f"- **Iterations:** {result.iterations}",
        f"- **Converged (collision-free reached):** {result.converged}",
        "",
    ]
    if result.proposals:
        lines += [
            "## Proposed retunes",
            "",
            "| Qubit | Original (GHz) | Proposed (GHz) | Δ (MHz) |",
            "| --- | --- | --- | --- |",
        ]
        for p in result.proposals:
            delta_mhz = (p.proposed_freq_ghz - p.original_freq_ghz) * 1e3
            lines.append(
                f"| {p.qubit_id} | {p.original_freq_ghz:.6f} | {p.proposed_freq_ghz:.6f} | "
                f"{delta_mhz:+.2f} |"
            )
        lines.append("")
    else:
        lines += ["No retuning was necessary or possible within the search budget.", ""]
    lines += ["## Assumptions", ""]
    lines += [f"- {a}" for a in result.assumptions]
    lines.append("")
    return "\n".join(lines)


def write_chip_optimize_report(
    result: ChipOptimizeResult,
    out_dir: str | Path,
    *,
    provenance: dict[str, object] | None = None,
) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "chip_optimize_report.json"
    md_path = out / "chip_optimize_report.md"
    proposal_path = out / "retune_proposal.json"
    payload = result.to_dict()
    payload["provenance"] = provenance or chip_report_provenance()
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        render_optimize_markdown(result) + "\n" + _PROVENANCE_MD, encoding="utf-8"
    )
    # Standalone machine-readable proposal so a later design run can consume
    # the retuned targets without parsing the whole report.
    proposal_path.write_text(
        json.dumps(
            {
                "schema": "textlayout.retune-proposal.v1",
                "lattice_name": result.lattice_name,
                "converged": result.converged,
                "violations_before": result.before.n_violations,
                "violations_after": result.after.n_violations,
                "proposals": [
                    {
                        "qubit_id": p.qubit_id,
                        "original_freq_ghz": p.original_freq_ghz,
                        "proposed_freq_ghz": p.proposed_freq_ghz,
                        "delta_mhz": (p.proposed_freq_ghz - p.original_freq_ghz) * 1e3,
                    }
                    for p in result.proposals
                ],
                "provenance": payload["provenance"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "retune_proposal": str(proposal_path),
    }
