"""HTML scientific report generator for superconducting quantum circuit devices."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STATUS_COLORS: dict[str, tuple[str, str]] = {
    "EXECUTED": ("#1b7a3d", "#d4edda"),
    "SKIPPED": ("#6c757d", "#e2e3e5"),
    "FAILED": ("#a71d2a", "#f8d7da"),
}


def _badge(status: str) -> str:
    """Return an inline HTML badge for a solver status."""
    fg, bg = _STATUS_COLORS.get(status, ("#333", "#eee"))
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;'
        f'font-weight:600;font-size:0.85em;color:{fg};background:{bg};">'
        f"{html.escape(status)}</span>"
    )


def _esc(v: Any) -> str:
    return html.escape(str(v)) if v is not None else "&mdash;"


def _param_rows(params: dict[str, Any]) -> str:
    """Build table rows from a flat dict of parameters."""
    rows: list[str] = []
    for key, val in sorted(params.items()):
        if isinstance(val, dict) and "value" in val:
            display = f'{val["value"]} {val.get("unit", "")}'.strip()
            method = val.get("method_label") or val.get("method", "")
            rows.append(f"<tr><td>{_esc(key)}</td><td>{_esc(display)}</td><td>{_esc(method)}</td></tr>")
        else:
            rows.append(f"<tr><td>{_esc(key)}</td><td>{_esc(val)}</td><td></td></tr>")
    return "\n".join(rows)


def _extraction_section(extraction: dict[str, Any]) -> str:
    """Render extraction results as an HTML table."""
    if not extraction:
        return "<p>No extraction data available.</p>"
    rows: list[str] = []
    for key, val in sorted(extraction.items()):
        if key in ("schema", "sidecar_path", "gds_path"):
            continue
        if isinstance(val, dict):
            for sub_key, sub_val in sorted(val.items()):
                if isinstance(sub_val, dict) and "value" in sub_val:
                    display = f'{sub_val["value"]} {sub_val.get("unit", "")}'.strip()
                    method = sub_val.get("method_label") or sub_val.get("method", "")
                    source = sub_val.get("source", "")
                    rows.append(
                        f"<tr><td>{_esc(key)}.{_esc(sub_key)}</td>"
                        f"<td>{_esc(display)}</td>"
                        f"<td>{_esc(method)}</td>"
                        f"<td>{_esc(source)}</td></tr>"
                    )
                else:
                    rows.append(
                        f"<tr><td>{_esc(key)}.{_esc(sub_key)}</td>"
                        f"<td>{_esc(sub_val)}</td><td></td><td></td></tr>"
                    )
        else:
            rows.append(f"<tr><td>{_esc(key)}</td><td>{_esc(val)}</td><td></td><td></td></tr>")
    if not rows:
        return "<p>No extraction quantities found.</p>"
    return (
        '<table class="data-table">'
        "<thead><tr><th>Quantity</th><th>Value</th><th>Method</th><th>Source</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _simulation_section(simulation: dict[str, Any]) -> str:
    """Render simulation evidence with status badges."""
    if not simulation:
        return "<p>No simulation data available.</p>"
    status = simulation.get("status", "SKIPPED").upper()
    solver = simulation.get("solver") or simulation.get("engine") or "unknown"
    parts = [f"<p><strong>Solver:</strong> {_esc(solver)} {_badge(status)}</p>"]

    if status == "EXECUTED":
        runtime = simulation.get("runtime_s") or simulation.get("runtime")
        if runtime is not None:
            parts.append(f"<p><strong>Runtime:</strong> {runtime} s</p>")
        output_files = simulation.get("output_files") or simulation.get("artifacts", [])
        if output_files:
            items = "".join(f"<li>{_esc(f)}</li>" for f in output_files)
            parts.append(f"<p><strong>Output files:</strong></p><ul>{items}</ul>")
        quantities = simulation.get("parsed_quantities") or simulation.get("metrics", {})
        if quantities:
            rows = "".join(
                f"<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>" for k, v in sorted(quantities.items())
            )
            parts.append(
                '<table class="data-table"><thead><tr><th>Quantity</th><th>Value</th></tr></thead>'
                f"<tbody>{rows}</tbody></table>"
            )
    elif status == "SKIPPED":
        reason = simulation.get("reason", "Solver not available")
        parts.append(f"<p><em>{_esc(reason)}</em></p>")
    elif status == "FAILED":
        error = simulation.get("error") or simulation.get("message", "Unknown error")
        parts.append(f'<p style="color:#a71d2a;"><strong>Error:</strong> {_esc(error)}</p>')

    return "\n".join(parts)


def _review_section(review: dict[str, Any]) -> str:
    """Render review committee verdict."""
    if not review:
        return "<p>No review data available.</p>"
    approved = review.get("approved", False)
    score = review.get("score", 0)
    errors = review.get("error_count", 0)
    warnings = review.get("warning_count", 0)
    verdict_color = "#1b7a3d" if approved else "#a71d2a"
    verdict_text = "APPROVED" if approved else "NOT APPROVED"
    parts = [
        f'<p style="font-size:1.2em;"><strong>Verdict: </strong>'
        f'<span style="color:{verdict_color};font-weight:700;">{verdict_text}</span></p>',
        f"<p><strong>Score:</strong> {score} / 100 "
        f"(errors: {errors}, warnings: {warnings})</p>",
    ]
    blockers = review.get("blockers", [])
    if blockers:
        items = "".join(
            f'<li style="color:#a71d2a;">{_esc(b.get("message", str(b)))}</li>' for b in blockers
        )
        parts.append(f"<p><strong>Blockers:</strong></p><ul>{items}</ul>")
    reviews = review.get("reviews", [])
    if reviews:
        rows = "".join(
            f"<tr><td>{_esc(r.get('reviewer', ''))}</td>"
            f"<td>{r.get('score', '')}</td>"
            f'<td>{"PASS" if r.get("passed") else "FAIL"}</td></tr>'
            for r in reviews
        )
        parts.append(
            '<table class="data-table"><thead><tr><th>Reviewer</th><th>Score</th><th>Result</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )
    return "\n".join(parts)


_CSS = """\
body { font-family: "Segoe UI", system-ui, -apple-system, sans-serif; margin: 0; padding: 0; color: #222; background: #f8f9fa; }
.header { background: #1a1d24; color: #fff; padding: 24px 32px; }
.header h1 { margin: 0 0 4px 0; font-size: 1.6em; }
.header .subtitle { color: #9ca3af; font-size: 0.95em; }
.container { max-width: 960px; margin: 0 auto; padding: 24px 32px; }
h2 { color: #1a1d24; border-bottom: 2px solid #dee2e6; padding-bottom: 6px; margin-top: 32px; }
.data-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.92em; }
.data-table th { background: #343a40; color: #fff; padding: 8px 12px; text-align: left; }
.data-table td { padding: 7px 12px; border-bottom: 1px solid #dee2e6; }
.data-table tbody tr:nth-child(even) { background: #f1f3f5; }
.data-table tbody tr:hover { background: #e9ecef; }
.footer { text-align: center; color: #6c757d; font-size: 0.82em; padding: 20px; margin-top: 40px; border-top: 1px solid #dee2e6; }
"""


def generate_report(
    sidecar: dict[str, Any],
    extraction: dict[str, Any] | None = None,
    simulation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    output_path: Path | str = Path("report.html"),
) -> Path:
    """Generate an HTML scientific report for a superconducting device and write it to *output_path*."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    device = sidecar.get("pcell") or sidecar.get("device") or "unknown device"
    gds_path = sidecar.get("gds_path", "")
    schema = sidecar.get("schema", "")
    info = sidecar.get("info", {})
    params = sidecar.get("parameters", sidecar.get("params", {}))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Device summary
    summary_rows = [
        f"<tr><td>Device</td><td>{_esc(device)}</td></tr>",
        f"<tr><td>GDS file</td><td>{_esc(gds_path)}</td></tr>",
        f"<tr><td>Schema</td><td>{_esc(schema)}</td></tr>",
    ]
    for k, v in sorted(info.items()):
        summary_rows.append(f"<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>")

    html_parts = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>Report: {html.escape(device)}</title>",
        f"<style>{_CSS}</style></head><body>",
        '<div class="header">',
        f"<h1>Scientific Report: {html.escape(device)}</h1>",
        f'<div class="subtitle">Generated {timestamp} &mdash; text-to-gds physics compiler</div>',
        "</div>",
        '<div class="container">',
        # Section 1: Device Summary
        "<h2>1. Device Summary</h2>",
        '<table class="data-table"><thead><tr><th>Property</th><th>Value</th></tr></thead>',
        f"<tbody>{''.join(summary_rows)}</tbody></table>",
        # Section 2: Layout Parameters
        "<h2>2. Layout Parameters</h2>",
    ]

    if params:
        html_parts.append(
            '<table class="data-table"><thead><tr><th>Parameter</th><th>Value</th><th>Method</th></tr></thead>'
            f"<tbody>{_param_rows(params)}</tbody></table>"
        )
    else:
        html_parts.append("<p>No layout parameters in sidecar.</p>")

    # Section 3: Extraction Results
    html_parts.append("<h2>3. Extraction Results</h2>")
    html_parts.append(_extraction_section(extraction or {}))

    # Section 4: Simulation Evidence
    html_parts.append("<h2>4. Simulation Evidence</h2>")
    html_parts.append(_simulation_section(simulation or {}))

    # Section 5: Review Verdict
    html_parts.append("<h2>5. Review Verdict</h2>")
    html_parts.append(_review_section(review or {}))

    html_parts.append("</div>")  # close container
    html_parts.append(
        '<div class="footer">text-to-gds &mdash; superconducting quantum circuit layout compiler</div>'
    )
    html_parts.append("</body></html>")

    output_path.write_text("\n".join(html_parts), encoding="utf-8")
    return output_path
