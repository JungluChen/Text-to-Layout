from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


WORKBENCH_APP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Text-to-GDS Live Workbench</title>
  <style>
    :root {
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", sans-serif;
      --bg: #f5f5f7;
      --panel: rgba(255,255,255,0.82);
      --panel-solid: #ffffff;
      --ink: #1d1d1f;
      --muted: #6e6e73;
      --line: rgba(0,0,0,0.12);
      --blue: #0071e3;
      --green: #34c759;
      --red: #ff3b30;
      --amber: #ff9f0a;
      --shadow: 0 24px 70px rgba(0,0,0,0.10);
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.92), rgba(245,245,247,0.98)),
        radial-gradient(circle at 20% 0%, rgba(0,113,227,0.10), transparent 32%),
        var(--bg);
      color: var(--ink);
    }
    main { max-width: 1480px; margin: 0 auto; padding: 22px; }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 18px;
    }
    h1 { font-size: 32px; line-height: 1.05; letter-spacing: 0; margin: 0; font-weight: 720; }
    .subhead { margin: 6px 0 0; color: var(--muted); font-size: 14px; }
    .shell {
      display: grid;
      grid-template-columns: 390px minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(28px) saturate(170%);
      border-radius: 24px;
      padding: 16px;
    }
    .controls { position: sticky; top: 16px; display: grid; gap: 14px; }
    form { display: grid; gap: 12px; margin: 0; }
    label span, .label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    textarea, input, select, button {
      width: 100%;
      font: inherit;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.94);
      color: var(--ink);
      padding: 11px 12px;
      outline: none;
    }
    textarea { min-height: 88px; resize: vertical; line-height: 1.35; }
    input:focus, textarea:focus, select:focus { border-color: rgba(0,113,227,0.75); box-shadow: 0 0 0 4px rgba(0,113,227,0.12); }
    button {
      border: 0;
      background: var(--blue);
      color: #fff;
      font-weight: 700;
      cursor: pointer;
      min-height: 46px;
      box-shadow: 0 12px 26px rgba(0,113,227,0.25);
    }
    button:disabled { opacity: 0.65; cursor: progress; }
    .two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .toggle {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 10px;
      align-items: center;
      padding: 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.7);
      border-radius: 16px;
    }
    .toggle input { width: 20px; height: 20px; accent-color: var(--blue); }
    .status-line { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.76);
      padding: 7px 10px;
      font-size: 12px;
      color: var(--muted);
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--amber); }
    .dot.ok { background: var(--green); }
    .dot.bad { background: var(--red); }
    .metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .metric {
      border-radius: 18px;
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      padding: 12px;
      min-height: 74px;
      min-width: 0;
      overflow: hidden;
    }
    .metric b {
      display: block;
      font-size: 18px;
      line-height: 1.18;
      letter-spacing: 0;
      margin-top: 6px;
      overflow-wrap: anywhere;
    }
    .metric span { color: var(--muted); font-size: 12px; }
    .artifact-list { display: grid; gap: 8px; }
    .artifact-list a {
      display: flex;
      justify-content: space-between;
      align-items: center;
      text-decoration: none;
      color: var(--ink);
      background: rgba(255,255,255,0.76);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px;
    }
    .artifact-list a::after { content: "Open"; color: var(--blue); font-size: 12px; }
    .stage { display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 16px; }
    .visual-stack { display: grid; gap: 16px; }
    .side-stack { display: grid; gap: 16px; }
    .viewport {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fff;
      overflow: hidden;
    }
    .layout-img { aspect-ratio: 1 / 1; object-fit: contain; display: block; }
    .plot-img { aspect-ratio: 16 / 10; object-fit: contain; display: block; }
    iframe.viewport { height: 540px; }
    h2 { font-size: 14px; margin: 0 0 10px; letter-spacing: 0; }
    pre {
      white-space: pre-wrap;
      overflow: auto;
      max-height: 420px;
      margin: 0;
      border-radius: 16px;
      background: #111113;
      color: #f5f5f7;
      padding: 14px;
      font-size: 12px;
      line-height: 1.45;
    }
    .empty {
      min-height: 240px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.48);
    }
    @media (max-width: 900px) {
      main { padding: 12px; }
      header, .shell, .stage, .two { grid-template-columns: 1fr; display: grid; }
      .controls { position: static; }
      iframe.viewport { height: 420px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Text-to-GDS Live Workbench</h1>
        <p class="subhead">Local superconducting layout, DRC, extraction, stack review, and simulation.</p>
      </div>
      <div class="status-line">
        <span class="chip"><i id="run-dot" class="dot"></i><span id="status">Idle</span></span>
        <span class="chip" id="adapter-chip">Simulator: Ideal JJ</span>
      </div>
    </header>

    <div class="shell">
      <aside class="panel controls">
        <form id="design-form">
          <label>
            <span>Prompt</span>
            <textarea id="prompt" aria-label="Design prompt">Design a 5 Ghz LJPA with wide bandwidth</textarea>
          </label>
          <div class="two">
            <label>
              <span>Output</span>
              <input id="output" value="ljpa_seed.gds" aria-label="Output GDS name">
            </label>
            <label>
              <span>Jc</span>
              <input id="jc" value="2.0" inputmode="decimal" aria-label="Critical current density">
            </label>
          </div>
          <label>
            <span>Simulator</span>
            <select id="simulator" aria-label="Simulator">
              <option value="mock_jj">Ideal JJ</option>
              <option value="JosephsonCircuits.jl">JosephsonCircuits.jl</option>
              <option value="josim">JoSIM transient</option>
              <option value="ngspice">ngspice</option>
            </select>
          </label>
          <div class="two">
            <label>
              <span>Analysis</span>
              <select id="analysis" aria-label="JosephsonCircuits analysis mode">
                <option value="auto">Auto</option>
                <option value="multiport-ljpa">Multiport LJPA</option>
                <option value="single-port-reflection">Single-port</option>
              </select>
            </label>
            <label>
              <span>Pump fraction</span>
              <input id="pump" value="0.017" inputmode="decimal" aria-label="Pump current fraction">
            </label>
          </div>
          <div class="two">
            <label>
              <span>Coupling fF</span>
              <input id="coupling" placeholder="auto" inputmode="decimal" aria-label="Coupling capacitance">
            </label>
            <label>
              <span>Resonator fF</span>
              <input id="resonator" placeholder="auto" inputmode="decimal" aria-label="Resonator capacitance">
            </label>
          </div>
          <div class="two">
            <label>
              <span>Flux Phi0</span>
              <input id="flux" value="0.0" inputmode="decimal" aria-label="Flux bias in Phi0">
            </label>
            <label>
              <span>SQUID asymmetry</span>
              <input id="asymmetry" value="0.0" inputmode="decimal" aria-label="SQUID asymmetry">
            </label>
          </div>
          <label class="toggle">
            <input id="optimize" type="checkbox">
            <span>Optimize geometry</span>
          </label>
          <button id="run-button" type="submit">Run Local Workflow</button>
        </form>

        <section>
          <h2>Metrics</h2>
          <div id="metrics" class="metric-grid">
            <div class="metric"><span>Status</span><b>Idle</b></div>
            <div class="metric"><span>DRC</span><b>--</b></div>
          </div>
        </section>

        <section>
          <h2>Artifacts</h2>
          <div id="artifacts" class="artifact-list"></div>
        </section>
      </aside>

      <section class="stage">
        <div class="visual-stack">
          <section class="panel">
            <h2>Layout</h2>
            <div id="layout-empty" class="empty">No layout</div>
            <img id="layout" class="viewport layout-img" alt="Generated layout screenshot" hidden>
          </section>
          <section class="panel">
            <h2>3D Stack</h2>
            <div id="stack-empty" class="empty">No stack</div>
            <iframe id="stack" class="viewport" title="3D stack viewer" hidden></iframe>
          </section>
        </div>
        <div class="side-stack">
          <section class="panel">
            <h2>Simulation Plot</h2>
            <div id="plot-empty" class="empty">No plot</div>
            <img id="plot" class="viewport plot-img" alt="Python-rendered simulation plot" hidden>
          </section>
          <section class="panel">
            <h2>Workbench</h2>
            <iframe id="workbench" class="viewport" title="Generated workbench"></iframe>
          </section>
          <section class="panel">
            <h2>JSON</h2>
            <pre id="json">{}</pre>
          </section>
        </div>
      </section>
    </div>
  </main>
  <script>
    const form = document.querySelector('#design-form');
    const statusEl = document.querySelector('#status');
    const runDot = document.querySelector('#run-dot');
    const runButton = document.querySelector('#run-button');
    const adapterChip = document.querySelector('#adapter-chip');
    const artifactsEl = document.querySelector('#artifacts');
    const metricsEl = document.querySelector('#metrics');
    const jsonEl = document.querySelector('#json');
    const workbenchEl = document.querySelector('#workbench');
    const stackEl = document.querySelector('#stack');
    const layoutEl = document.querySelector('#layout');
    const plotEl = document.querySelector('#plot');

    function artifactUrl(path) {
      return path ? `/api/artifact?path=${encodeURIComponent(path)}` : '';
    }

    function optionalNumber(selector) {
      const value = document.querySelector(selector).value.trim();
      return value ? Number(value) : null;
    }

    function showMedia(element, emptySelector, path) {
      const empty = document.querySelector(emptySelector);
      if (!path) {
        element.hidden = true;
        empty.hidden = false;
        return;
      }
      element.src = artifactUrl(path);
      element.hidden = false;
      empty.hidden = true;
    }

    function adapterPayload(payload) {
      const adapter = payload?.simulation?.adapter_result;
      return adapter && adapter.result ? adapter.result : {};
    }

    function metricRows(payload) {
      const sim = payload.simulation || {};
      const adapter = adapterPayload(payload);
      const rows = [
        ['Status', payload.status || 'completed'],
        ['DRC', payload.drc?.status || '--'],
        ['Process DRC', payload.process_drc?.status || '--'],
        ['Magic', payload.magic?.status || '--'],
        ['Engine', sim.engine || '--']
      ];
      if (adapter.peak_s21_gain_db !== undefined) {
        rows.push(['Peak S21', `${adapter.peak_s21_gain_db.toFixed(3)} dB`]);
        rows.push(['S21 Freq', `${adapter.peak_s21_frequency_ghz.toFixed(4)} GHz`]);
        rows.push(['3 dB BW', `${adapter.bandwidth_3db_mhz.toFixed(3)} MHz`]);
      } else if (sim.physical_performance?.flux_tuning?.operating_point) {
        const flux = sim.physical_performance.flux_tuning.operating_point;
        rows.push(['Flux Bias', `${Number(flux.flux_phi0 || 0).toFixed(4)} Phi0`]);
        rows.push(['Flux Freq', `${Number(flux.resonant_frequency_ghz || 0).toFixed(4)} GHz`]);
        rows.push(['Flux Ic', `${Number(flux.critical_current_ua || 0).toFixed(4)} uA`]);
      } else if (adapter.peak_gain_db !== undefined) {
        rows.push(['Peak S11', `${adapter.peak_gain_db.toFixed(3)} dB`]);
        rows.push(['3 dB BW', `${adapter.bandwidth_3db_mhz.toFixed(3)} MHz`]);
      } else {
        rows.push(['Ic', `${Number(sim.critical_current_ua || 0).toFixed(4)} uA`]);
        rows.push(['Lj', `${Number(sim.josephson_inductance_ph || 0).toFixed(2)} pH`]);
      }
      return rows;
    }

    function renderMetrics(payload) {
      metricsEl.innerHTML = metricRows(payload)
        .map(([label, value]) => `<div class="metric"><span>${label}</span><b>${value}</b></div>`)
        .join('');
    }

    function renderArtifacts(payload) {
      const links = [
        ['GDS', payload.compile?.gds_path],
        ['Layout PNG', payload.compile?.screenshot_path],
        ['3D Stack', payload.preview?.html_path],
        ['Simulation Plot', payload.simulation?.plot_path],
        ['Scientific PNG', payload.simulation?.scientific_plot_path],
        ['Scientific CSV', payload.simulation?.scientific_plot?.csv_path],
        ['CAD SVG', payload.cad?.outputs?.layout_svg],
        ['CAD DXF', payload.cad?.outputs?.layout_dxf],
        ['CAD STL', payload.cad?.outputs?.stack_stl],
        ['CAD GLB', payload.cad?.outputs?.stack_glb],
        ['Workbench', payload.workbench?.html_path],
        ['Simulation JSON', payload.simulation?.result_path],
        ['Extraction JSON', payload.extraction?.result_path],
        ['CAD JSON', payload.cad?.report_path],
        ['Validation JSON', payload.validation?.report_path],
        ['Magic JSON', payload.magic?.report_path],
        ['Magic TCL', payload.magic?.script_path],
        ['Magic SPICE', payload.magic?.spice_path]
      ].filter(([, path]) => path);
      artifactsEl.innerHTML = links
        .map(([label, path]) => `<a href="${artifactUrl(path)}" target="_blank" rel="noreferrer">${label}</a>`)
        .join('');
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      statusEl.textContent = 'Running';
      runDot.className = 'dot';
      runButton.disabled = true;
      artifactsEl.textContent = '';
      jsonEl.textContent = '';
      adapterChip.textContent = `Simulator: ${document.querySelector('#simulator').value}`;
      const response = await fetch('/api/design-workflow', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          prompt: document.querySelector('#prompt').value,
          output_name: document.querySelector('#output').value,
          simulator: document.querySelector('#simulator').value,
          optimize: document.querySelector('#optimize').checked,
          jc_ua_per_um2: Number(document.querySelector('#jc').value || 2.0),
          analysis_mode: document.querySelector('#analysis').value,
          pump_current_fraction: Number(document.querySelector('#pump').value || 0.017),
          coupling_capacitance_ff: optionalNumber('#coupling'),
          resonator_capacitance_ff: optionalNumber('#resonator'),
          flux_bias_phi0: Number(document.querySelector('#flux').value || 0.0),
          squid_asymmetry: Number(document.querySelector('#asymmetry').value || 0.0)
        })
      });
      const payload = await response.json();
      jsonEl.textContent = JSON.stringify(payload, null, 2);
      runButton.disabled = false;
      if (!response.ok) {
        statusEl.textContent = payload.error || 'Failed';
        runDot.className = 'dot bad';
        return;
      }
      statusEl.textContent = payload.status;
      runDot.className = 'dot ok';
      workbenchEl.src = artifactUrl(payload.workbench.html_path);
      showMedia(layoutEl, '#layout-empty', payload.compile.screenshot_path);
      showMedia(stackEl, '#stack-empty', payload.preview.html_path);
      showMedia(plotEl, '#plot-empty', payload.simulation.plot_path);
      renderMetrics(payload);
      renderArtifacts(payload);
    });

    form.addEventListener('input', () => {
      adapterChip.textContent = `Simulator: ${document.querySelector('#simulator').value}`;
    });
  </script>
</body>
</html>
"""


def make_workbench_handler() -> type[BaseHTTPRequestHandler]:
    from text_to_gds import server

    class WorkbenchHandler(BaseHTTPRequestHandler):
        server_version = "TextToGDSWorkbench/0.1"

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path_value: str) -> None:
            raw = Path(path_value)
            candidate = raw if raw.is_absolute() else server.ARTIFACT_ROOT / raw.name
            artifact_root = server.ARTIFACT_ROOT.resolve()
            resolved = candidate.resolve()
            if resolved != artifact_root and artifact_root not in resolved.parents:
                self._send_json({"error": "artifact path outside workspace"}, HTTPStatus.FORBIDDEN)
                return
            if not resolved.is_file():
                self._send_json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND)
                return
            body = resolved.read_bytes()
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path in {"/", "/index.html"}:
                self._send_html(WORKBENCH_APP_HTML)
                return
            if path == "/api/artifact":
                query = parse_qs(parsed.query)
                path_value = query.get("path", [""])[0]
                self._send_file(path_value)
                return
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/design-workflow":
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            length = int(self.headers.get("content-length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                workflow = (
                    server.run_optimized_design_workflow
                    if bool(payload.get("optimize"))
                    else server.run_design_workflow
                )
                def _opt_float(key: str) -> "float | None":
                    val = payload.get(key)
                    return float(val) if val is not None else None
                result = workflow(
                    prompt=str(payload.get("prompt", "Design a 5 Ghz LJPA with wilde bandwidth")),
                    output_name=str(payload.get("output_name", "ljpa_seed.gds")),
                    parameters=payload.get("parameters") if isinstance(payload.get("parameters"), dict) else None,
                    jc_ua_per_um2=float(payload.get("jc_ua_per_um2", 2.0)),
                    simulator=str(payload.get("simulator", "mock_jj")),
                    analysis_mode=str(payload.get("analysis_mode", "auto")),
                    pump_current_fraction=float(payload.get("pump_current_fraction", 0.017)),
                    coupling_capacitance_ff=_opt_float("coupling_capacitance_ff"),
                    resonator_capacitance_ff=_opt_float("resonator_capacitance_ff"),
                    flux_bias_phi0=float(payload.get("flux_bias_phi0", 0.0)),
                    squid_asymmetry=float(payload.get("squid_asymmetry", 0.0)),
                    # Design-intent physics inputs
                    epsilon_r=_opt_float("epsilon_r"),
                    substrate_thickness_um=_opt_float("substrate_thickness_um"),
                    ground_width_um=_opt_float("ground_width_um"),
                    package_clearance_um=_opt_float("package_clearance_um"),
                    pump_frequency_ghz=_opt_float("pump_frequency_ghz"),
                    pump_power_dbm=_opt_float("pump_power_dbm"),
                    pump_mode=str(payload["pump_mode"]) if payload.get("pump_mode") else None,
                    substrate=str(payload["substrate"]) if payload.get("substrate") else None,
                )
            except Exception as error:  # pragma: no cover - returned to browser/user
                self._send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(result)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    return WorkbenchHandler


def create_workbench_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_workbench_handler())


def serve_workbench(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = create_workbench_server(host=host, port=port)
    print(f"Text-to-GDS live workbench: http://{host}:{httpd.server_port}")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
