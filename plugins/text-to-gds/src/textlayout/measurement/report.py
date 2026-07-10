"""Render measurement-comparison residuals and calibration to JSON/Markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from textlayout.measurement.models import CalibrationFile, ResidualRecord


class QuantityStats(TypedDict):
    """Per-quantity residual statistics."""

    n: int
    mean_error_pct: float
    max_abs_error_pct: float


class ComparisonSummary(TypedDict):
    """Coverage + status block for a prediction-vs-measurement comparison.

    ``n_unmatched_predictions`` and ``n_unmatched_measurements`` are reported
    separately: a run that predicted 40 devices and measured 2 is not the same
    evidence as one that measured 40 and predicted 2, and a single
    ``n_unmatched`` cannot distinguish them.
    """

    comparison_status: str
    labels: list[str]
    n_predictions: int
    n_measurements: int
    n_matched: int
    n_unmatched: int  # retained for back-compat: max(pred, meas) - matched
    n_unmatched_predictions: int
    n_unmatched_measurements: int
    coverage_pct: float
    quantities_compared: list[str]
    per_quantity: dict[str, QuantityStats]
    synthetic_data: bool
    pdk_names: list[str]
    matched_by: str
    warning: str


def write_comparison_report(residuals: list[ResidualRecord], out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "measurement_comparison.json"
    md_path = out / "measurement_comparison.md"
    json_path.write_text(
        json.dumps([r.model_dump(mode="json") for r in residuals], indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_comparison_markdown(residuals), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


#: Comparison-level statuses (Sprint 5 vocabulary).
COMPARISON_MATCHED = "MEASUREMENT_COMPARED"
COMPARISON_PARTIAL = "PARTIAL_MEASUREMENT_MATCH"
COMPARISON_INSUFFICIENT = "INSUFFICIENT_MEASUREMENT_DATA"


def build_comparison_summary(
    residuals: list[ResidualRecord],
    *,
    n_predictions: int,
    n_measurements: int,
    n_matched: int,
    any_synthetic: bool,
    pdk_names: list[str],
) -> ComparisonSummary:
    """Typed summary block for the comparison bundle: counts, stats, statuses."""
    if n_matched == 0:
        status = COMPARISON_INSUFFICIENT
    elif n_matched < max(n_predictions, n_measurements):
        status = COMPARISON_PARTIAL
    else:
        status = COMPARISON_MATCHED
    per_quantity: dict[str, QuantityStats] = {}
    for r in residuals:
        bucket = per_quantity.setdefault(
            r.quantity, QuantityStats(n=0, mean_error_pct=0.0, max_abs_error_pct=0.0)
        )
        bucket["n"] += 1
        bucket["mean_error_pct"] += r.error_percent
        bucket["max_abs_error_pct"] = max(bucket["max_abs_error_pct"], abs(r.error_percent))
    for bucket in per_quantity.values():
        bucket["mean_error_pct"] /= bucket["n"]
    labels = [status, "NOT_FABRICATION_READY"]
    if any_synthetic:
        labels.insert(1, "SYNTHETIC_MEASUREMENT")
    # Coverage is measured against the side that has more devices: matching 2 of
    # 40 predictions is 5% coverage, never 100%, even if both measurements paired.
    denominator = max(n_predictions, n_measurements)
    coverage_pct = 100.0 * n_matched / denominator if denominator else 0.0
    return ComparisonSummary(
        comparison_status=status,
        labels=labels,
        n_predictions=n_predictions,
        n_measurements=n_measurements,
        n_matched=n_matched,
        n_unmatched=denominator - n_matched,
        n_unmatched_predictions=n_predictions - n_matched,
        n_unmatched_measurements=n_measurements - n_matched,
        coverage_pct=coverage_pct,
        quantities_compared=sorted({r.quantity for r in residuals}),
        per_quantity=per_quantity,
        synthetic_data=any_synthetic,
        pdk_names=sorted(set(pdk_names)),
        matched_by="design_hash",
        warning=(
            "SYNTHETIC measurement data — demonstrates the pipeline; says nothing "
            "about any real process. Not fabrication-ready."
            if any_synthetic
            else "Not fabrication-ready without foundry qualification."
        ),
    )


def write_comparison_bundle(
    residuals: list[ResidualRecord],
    summary: ComparisonSummary,
    out_dir: str | Path,
) -> dict[str, str]:
    """Sprint-5 artifact set: residuals CSV + full comparison report JSON/MD."""
    import csv as _csv

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "measurement_residuals.csv"
    json_path = out / "measurement_comparison_report.json"
    md_path = out / "measurement_comparison_report.md"

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = _csv.writer(handle)
        writer.writerow(
            [
                "device_id",
                "design_hash",
                "quantity",
                "simulated_value",
                "measured_value",
                "unit",
                "error_absolute",
                "error_percent",
            ]
        )
        for r in residuals:
            writer.writerow(
                [
                    r.device_id,
                    r.design_hash,
                    r.quantity,
                    f"{r.simulated_value:.9g}",
                    f"{r.measured_value:.9g}",
                    r.unit,
                    f"{r.error_absolute:.9g}",
                    f"{r.error_percent:.4f}",
                ]
            )

    payload = {
        "schema": "textlayout.measurement-comparison-report.v1",
        "summary": summary,
        "residuals": [r.model_dump(mode="json") for r in residuals],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Measurement comparison report",
        "",
        f"- **Status:** **{summary['comparison_status']}** "
        f"({', '.join(summary['labels'])})",
        f"- Predictions: {summary['n_predictions']} · Measurements: "
        f"{summary['n_measurements']} · Matched: {summary['n_matched']} · "
        f"Unmatched: {summary['n_unmatched']} (matched by design_hash)",
        f"- **Comparison coverage: {summary['coverage_pct']:.1f}%** "
        f"({summary['n_unmatched_predictions']} prediction(s) and "
        f"{summary['n_unmatched_measurements']} measurement(s) unmatched)",
        f"- Quantities compared: "
        f"{', '.join(summary['quantities_compared']) or '(none)'}",
        f"- PDKs behind the predictions: "
        f"{', '.join(summary['pdk_names']) or '(not recorded)'}",
        f"- {summary['warning']}",
        "",
        "## Per-quantity summary",
        "",
        "| Quantity | N | Mean error % | Max |error| % |",
        "| --- | --- | --- | --- |",
    ]
    for quantity, stats in summary["per_quantity"].items():
        md.append(
            f"| {quantity} | {stats['n']} | {stats['mean_error_pct']:+.2f}% | "
            f"{stats['max_abs_error_pct']:.2f}% |"
        )
    md += ["", render_comparison_markdown(residuals)]
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {
        "residuals_csv": str(csv_path),
        "json": str(json_path),
        "markdown": str(md_path),
    }


def render_comparison_markdown(residuals: list[ResidualRecord]) -> str:
    lines: list[str] = ["# Simulation-vs-measurement residuals", ""]
    if not residuals:
        lines += ["No comparable (prediction, measurement) pairs were found.", ""]
        return "\n".join(lines)
    lines += [
        "| Device | Quantity | Simulated | Measured | Unit | Error | Error % |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in residuals:
        lines.append(
            f"| {r.device_id} | {r.quantity} | {r.simulated_value:.6g} | "
            f"{r.measured_value:.6g} | {r.unit} | {r.error_absolute:+.4g} | "
            f"{r.error_percent:+.2f}% |"
        )
    lines.append("")
    return "\n".join(lines)


def write_calibration_report(calibration: CalibrationFile, out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / "calibration_report.md"
    md_path.write_text(render_calibration_markdown(calibration), encoding="utf-8")
    return {"markdown": str(md_path)}


def render_calibration_markdown(calibration: CalibrationFile) -> str:
    c = calibration.corrections
    lines: list[str] = [
        "# Measurement calibration report",
        "",
        f"- **Fitted from {calibration.n_records} device(s):** "
        f"{', '.join(calibration.source_device_ids)}",
        f"- **Synthetic:** {calibration.synthetic}"
        + (" (SYNTHETIC — do not apply to production)" if calibration.synthetic else ""),
        "",
        "## Correction factors",
        "",
        "| Factor | Value | N pairs |",
        "| --- | --- | --- |",
    ]

    def row(label: str, value: float | None, n: int) -> str:
        formatted = f"{value:.4f}" if value is not None else "—"
        return f"| {label} | {formatted} | {n} |"

    lines += [
        row("capacitance_scale", c.capacitance_scale, c.n_capacitance_pairs),
        row("inductance_scale", c.inductance_scale, c.n_inductance_pairs),
        row("loss_tangent_scale", c.loss_tangent_scale, c.n_loss_pairs),
        row("jc_scale", c.jc_scale, c.n_jc_pairs),
    ]
    if c.jc_scale_sigma_pct is not None:
        lines.append(f"| jc_scale_sigma_pct | {c.jc_scale_sigma_pct:.2f}% | {c.n_jc_pairs} |")
    lines += ["", "## What each factor means", ""]
    lines += [
        "- `capacitance_scale`: mean(measured C / simulated C). Multiply future "
        "capacitance predictions by this factor.",
        "- `inductance_scale`: mean(measured L / simulated L).",
        "- `loss_tangent_scale`: mean(predicted Q / measured Q). >1 means the real "
        "process has more loss than the EPR materials DB assumed — scale up "
        "`tan_delta` values in `textlayout.epr.materials` by this factor.",
        "- `jc_scale`: implied Jc correction from frequency residuals "
        "(assumes f ~ sqrt(Jc/C)). Multiply `JJProcessModel.target_jc_ua_per_um2` "
        "by this factor for future yield predictions on this process.",
        "- `jc_scale_sigma_pct`: sample spread of jc_scale across devices — an "
        "updated `wafer_jc_sigma_pct` estimate for `textlayout.yield_model`.",
        "",
        "## Path from simulation toy to fab-calibrated design tool",
        "",
        "Every other loop in this project (EPR participation, JJ yield, PDK "
        "process parameters) starts from illustrative, literature-scale "
        "numbers. This calibration is the mechanism that replaces them with "
        "real, process-specific values once fabricated devices come back "
        "from the fridge — feed the resulting `capacitance_scale`/"
        "`inductance_scale`/`loss_tangent_scale`/`jc_scale` back into the "
        "materials DB and process model, and every downstream estimate "
        "becomes measurement-grounded instead of illustrative.",
        "",
    ]
    if calibration.notes:
        lines += ["## Notes", ""]
        lines += [f"- {n}" for n in calibration.notes]
        lines.append("")
    return "\n".join(lines)
