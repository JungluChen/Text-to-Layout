"""Render an :class:`EPRResult` to JSON and Markdown evidence artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from textlayout.epr.models import EPRResult


def write_epr_report(result: EPRResult, out_dir: str | Path) -> dict[str, str]:
    """Write ``epr_report.json`` and ``epr_report.md``; return their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "epr_report.json"
    md_path = out / "epr_report.md"
    json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_markdown(result: EPRResult) -> str:
    lines: list[str] = [
        f"# EPR / loss-participation report — {result.component}",
        "",
        f"- **Backend:** `{result.backend}`",
        f"- **Status:** **{result.status}**",
        f"- **Frequency:** {result.frequency_ghz} GHz" if result.frequency_ghz else "",
        f"- **Generated:** {result.timestamp}",
        "",
    ]
    if result.status == "EPR_SKIPPED_SOLVER_ABSENT":
        lines += [
            "The requested EPR solver stack is not installed. No participation or",
            "coherence numbers are claimed.",
            "",
        ]
    if result.participations:
        lines += [
            "## Participation by loss channel",
            "",
            "| Region | Material | p_electric | tanδ | Q limit | T1 limit (µs) | Confidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for p in result.participations:
            q = f"{p.q_limit:.3e}" if p.q_limit else "—"
            t1 = f"{p.t1_limit_us:.2f}" if p.t1_limit_us else "—"
            lines.append(
                f"| {p.region} | {p.material} | {p.p_electric:.3e} | "
                f"{p.tan_delta:.1e} | {q} | {t1} | {p.confidence:.2f} |"
            )
        lines.append("")
    if result.coherence:
        c = result.coherence
        lines += [
            "## Coherence estimate",
            "",
            f"- **Q_total = 1/Σ p·tanδ = {c.q_total:.3e}**",
            f"- **T1 = Q/ω = {c.t1_total_us:.2f} µs** at {c.frequency_ghz} GHz",
            f"- **Dominant loss channel:** `{c.dominant_channel}`",
            f"- **Improve first:** {c.recommendation}",
            "",
            "### Sensitivity ranking",
            "",
            "| Region | p_electric | tanδ | Loss fraction |",
            "| --- | --- | --- | --- |",
        ]
        for row in c.sensitivity_ranking:
            lines.append(
                f"| {row['region']} | {float(row['p_electric']):.3e} | "
                f"{float(row['tan_delta']):.1e} | {float(row['loss_fraction']):.1%} |"
            )
        lines.append("")
    if result.assumptions:
        lines += ["## Assumptions", ""]
        lines += [f"- {a}" for a in result.assumptions]
        lines.append("")
    lines += [
        "## Honesty statement",
        "",
        "Capacitance/impedance accuracy does **not** imply coherence accuracy.",
        "An `EPR_ANALYTICAL_ONLY` participation model ranks loss channels; it does",
        "not predict absolute T1. Only `FIELD_ENERGY_IMPORTED`/`EPR_EXECUTED`",
        "participations plus",
        "process-measured loss tangents (see the measurement-calibration loop)",
        "justify quantitative coherence claims.",
        "",
    ]
    return "\n".join(line for line in lines if line is not None)
