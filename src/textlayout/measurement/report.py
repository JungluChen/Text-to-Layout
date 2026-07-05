"""Render measurement-comparison residuals and calibration to JSON/Markdown."""

from __future__ import annotations

import json
from pathlib import Path

from textlayout.measurement.models import CalibrationFile, ResidualRecord


def write_comparison_report(
    residuals: list[ResidualRecord], out_dir: str | Path
) -> dict[str, str]:
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
