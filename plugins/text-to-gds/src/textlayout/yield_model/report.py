"""Render a :class:`YieldResult` to JSON and Markdown evidence artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from textlayout.yield_model.models import YieldResult


def write_yield_report(result: YieldResult, out_dir: str | Path) -> dict[str, str]:
    """Write ``{analysis}_yield_report.{json,md}``; return their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{result.analysis}_yield_report"
    json_path = out / f"{stem}.json"
    md_path = out / f"{stem}.md"
    json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_markdown(result: YieldResult) -> str:
    s = result.statistics
    lines: list[str] = [
        f"# JJ yield report — {result.analysis}",
        "",
        f"- **Process calibration:** `{result.process.calibration}`"
        + (" (SYNTHETIC — not foundry-measured)" if result.synthetic else ""),
        f"- **Target:** {result.target.target_ghz} GHz ± {result.target.tolerance_mhz} MHz",
        f"- **Samples:** {s.n_samples}",
        f"- **Seed:** {result.seed} (rerun with the same seed for identical output)",
        "",
        "## Frequency distribution",
        "",
        f"- Mean: {s.mean_ghz:.4f} GHz, σ = {s.sigma_mhz:.2f} MHz",
        f"- p05 / p50 / p95: {s.p05_ghz:.4f} / {s.p50_ghz:.4f} / {s.p95_ghz:.4f} GHz",
        f"- Range: {s.min_ghz:.4f} – {s.max_ghz:.4f} GHz",
        "",
        "## Yield",
        "",
        f"- **Per-junction hit rate: {result.yield_pct:.2f}%** "
        f"(95% CI: {result.yield_ci95_pct[0]:.2f}–{result.yield_ci95_pct[1]:.2f}%)",
    ]
    if result.n_qubits_per_chip is not None and result.chip_yield_ci95_pct is not None:
        lines += [
            f"- **Chip yield (all {result.n_qubits_per_chip} qubits in spec): "
            f"{result.chip_yield_pct:.4f}%** "
            f"(95% CI: {result.chip_yield_ci95_pct[0]:.4f}"
            f"–{result.chip_yield_ci95_pct[1]:.4f}%)",
            "",
            f"Independent per-qubit variation compounds: a per-qubit hit rate of "
            f"{result.yield_pct:.1f}% does not imply a comparable chip yield when "
            f"{result.n_qubits_per_chip} qubits must simultaneously land in spec.",
        ]
    lines += [
        "",
        "## Process model",
        "",
        f"- Target Jc: {result.process.target_jc_ua_per_um2} µA/µm²",
        f"- Wafer-level σ: {result.process.wafer_jc_sigma_pct}%",
        f"- Local (junction-to-junction) σ: {result.process.local_jc_sigma_pct}%",
        f"- Lithography CD σ: {result.process.cd_sigma_nm} nm",
        f"- Source: {result.process.source}",
        "",
        "## Worst-case corners",
        "",
        "| Label | Frequency (GHz) | Jc (µA/µm²) | Area (µm²) | Ic (µA) | LJ (nH) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for corner in result.worst_corners:
        lines.append(
            f"| {corner.label} | {corner.frequency_ghz:.4f} | {corner.jc_ua_per_um2:.4g} | "
            f"{corner.area_um2:.4g} | {corner.ic_ua:.4g} | {corner.lj_nh:.4g} |"
        )
    lines += ["", "## Assumptions", ""]
    lines += [f"- {a}" for a in result.assumptions]
    lines += [
        "",
        "## Why one SQUID loop is not enough",
        "",
        "A single drawn SQUID/junction proves *geometry*, not *manufacturability*.",
        "Real fabrication has wafer-scale Jc drift and junction-to-junction local",
        "spread; both map directly into qubit-frequency spread through",
        "`f = 1/(2*pi*sqrt(LJ*C))`. A chip with many qubits requires each one to",
        "land in its target window *simultaneously* — independent per-qubit yield",
        "compounds multiplicatively, which is why scaling to N qubits is a yield",
        "problem, not just a layout problem.",
        "",
    ]
    return "\n".join(lines)
