from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _link(path_value: str | None, label: str) -> str:
    if not path_value:
        return f"<span>{html.escape(label)}</span>"
    path = Path(path_value)
    href = path.resolve().as_uri() if path.exists() else html.escape(path_value)
    return f'<a href="{href}">{html.escape(label)}</a>'


def _status_class(status: str | None) -> str:
    if status == "passed":
        return "ok"
    if status in {"failed", "error"}:
        return "bad"
    return "warn"


def write_design_workbench(
    *,
    prompt: str,
    plan: dict[str, Any],
    compiled: dict[str, Any],
    drc: dict[str, Any],
    process_drc: dict[str, Any],
    extraction: dict[str, Any],
    preview: dict[str, Any],
    simulation: dict[str, Any],
    html_path: str | Path,
) -> dict[str, Any]:
    """Write a local HTML workbench for prompt, layout, DRC, extraction, and simulation."""
    html_path = Path(html_path)
    screenshot_uri = Path(compiled["screenshot_path"]).resolve().as_uri()
    stack_preview_uri = Path(preview["html_path"]).resolve().as_uri()
    target = plan.get("target", {})
    questions = plan.get("clarifying_questions", [])
    parameters = extraction.get("parameters", {})
    impacts = extraction.get("performance_impacts", [])
    artifacts = [
        ("GDS", compiled.get("gds_path")),
        ("Layout PNG", compiled.get("screenshot_path")),
        ("Sidecar JSON", compiled.get("sidecar_path")),
        ("DRC JSON", drc.get("report_path")),
        ("Process DRC JSON", process_drc.get("report_path")),
        ("Extraction JSON", extraction.get("result_path")),
        ("Simulation JSON", simulation.get("result_path")),
        ("2.5D Stack HTML", preview.get("html_path")),
        ("2.5D Stack JSON", preview.get("json_path")),
    ]

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Text-to-GDS Workbench</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, sans-serif;
      --ink: #0f172a;
      --muted: #475569;
      --line: #cbd5e1;
      --panel: #ffffff;
      --bg: #f8fafc;
      --ok: #15803d;
      --bad: #b91c1c;
      --warn: #a16207;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); }}
    main {{ max-width: 1360px; margin: 0 auto; padding: 20px; }}
    header {{ display: grid; gap: 6px; margin-bottom: 16px; }}
    h1 {{ font-size: 24px; line-height: 1.2; margin: 0; }}
    h2 {{ font-size: 15px; margin: 0 0 10px; }}
    p {{ margin: 0; color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: 360px 1fr; gap: 14px; align-items: start; }}
    .stack {{ display: grid; gap: 14px; }}
    section {{ background: var(--panel); border: 1px solid var(--line); padding: 14px; }}
    .visuals {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    img, iframe {{ width: 100%; border: 1px solid var(--line); background: white; }}
    img {{ aspect-ratio: 1 / 1; object-fit: contain; }}
    iframe {{ height: 520px; }}
    dl {{ display: grid; grid-template-columns: 150px 1fr; gap: 7px 12px; margin: 0; }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; }}
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin: 5px 0; }}
    code {{ font-family: Consolas, monospace; font-size: 12px; }}
    .pill {{ display: inline-block; padding: 3px 8px; border: 1px solid currentColor; font-size: 12px; }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    .warn {{ color: var(--warn); }}
    .json {{ white-space: pre-wrap; overflow: auto; max-height: 360px; background: #f1f5f9; padding: 10px; }}
    @media (max-width: 980px) {{
      .grid, .visuals {{ grid-template-columns: 1fr; }}
      iframe {{ height: 420px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Text-to-GDS Workbench</h1>
      <p>{html.escape(prompt)}</p>
    </header>
    <div class="grid">
      <div class="stack">
        <section>
          <h2>Target</h2>
          <dl>
            <dt>Type</dt><dd>{html.escape(str(target.get("kind", "unknown")))}</dd>
            <dt>Frequency</dt><dd>{html.escape(str(target.get("center_frequency_ghz")))} GHz</dd>
            <dt>Bandwidth</dt><dd>{html.escape(str(target.get("bandwidth_mhz")))} MHz</dd>
            <dt>Gain</dt><dd>{html.escape(str(target.get("gain_db")))} dB</dd>
            <dt>Impedance</dt><dd>{html.escape(str(target.get("impedance_ohm")))} ohm</dd>
          </dl>
        </section>
        <section>
          <h2>Status</h2>
          <p><span class="pill {_status_class(drc.get("status"))}">DRC {html.escape(str(drc.get("status")))}</span></p>
          <p><span class="pill {_status_class(process_drc.get("status"))}">Process DRC {html.escape(str(process_drc.get("status")))}</span></p>
          <p><span class="pill warn">Simulation {html.escape(str(simulation.get("engine")))}</span></p>
        </section>
        <section>
          <h2>Clarifications</h2>
          <ul>{''.join(f'<li>{html.escape(str(q))}</li>' for q in questions)}</ul>
        </section>
        <section>
          <h2>Artifacts</h2>
          <ul>{''.join(f'<li>{_link(path, label)}</li>' for label, path in artifacts)}</ul>
        </section>
      </div>
      <div class="stack">
        <section class="visuals">
          <div>
            <h2>Layout</h2>
            <img src="{screenshot_uri}" alt="Generated layout screenshot">
          </div>
          <div>
            <h2>2.5D Stack</h2>
            <iframe src="{stack_preview_uri}" title="2.5D stack preview"></iframe>
          </div>
        </section>
        <section>
          <h2>Performance-Relevant Parameters</h2>
          <dl>{''.join(f'<dt>{html.escape(str(k))}</dt><dd>{html.escape(str(v))}</dd>' for k, v in parameters.items())}</dl>
        </section>
        <section>
          <h2>Parameter Impact</h2>
          <ul>{''.join(f'<li>{html.escape(str(item))}</li>' for item in impacts)}</ul>
        </section>
        <section>
          <h2>Simulation Result</h2>
          <div class="json">{html.escape(json.dumps(simulation, indent=2))}</div>
        </section>
      </div>
    </div>
  </main>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")
    return {
        "schema": "text-to-gds.workbench.v0",
        "html_path": str(html_path),
    }
