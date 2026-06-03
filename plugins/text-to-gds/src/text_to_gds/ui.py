from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


WORKBENCH_APP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Text-to-GDS Live Workbench</title>
  <style>
    :root { font-family: Arial, sans-serif; color: #0f172a; background: #f8fafc; }
    body { margin: 0; }
    main { max-width: 1280px; margin: 0 auto; padding: 20px; }
    h1 { font-size: 24px; margin: 0 0 12px; }
    form { display: grid; grid-template-columns: 1fr 180px 140px 120px; gap: 10px; margin-bottom: 14px; }
    input, button { font: inherit; padding: 10px; border: 1px solid #94a3b8; background: white; }
    button { background: #1d4ed8; color: white; border-color: #1d4ed8; cursor: pointer; }
    label { display: inline-flex; align-items: center; gap: 8px; border: 1px solid #94a3b8; background: white; padding: 10px; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 14px; align-items: start; }
    section { background: white; border: 1px solid #cbd5e1; padding: 14px; }
    h2 { font-size: 15px; margin: 0 0 10px; }
    pre { white-space: pre-wrap; overflow: auto; max-height: 520px; background: #f1f5f9; padding: 10px; }
    iframe, img { width: 100%; border: 1px solid #cbd5e1; background: white; }
    iframe { height: 620px; }
    img { aspect-ratio: 1 / 1; object-fit: contain; }
    a { color: #1d4ed8; }
    @media (max-width: 900px) {
      form, .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <h1>Text-to-GDS Live Workbench</h1>
    <form id="design-form">
      <input id="prompt" value="Design a 5 Ghz LJPA with wilde bandwidth" aria-label="Design prompt">
      <input id="output" value="ljpa_seed.gds" aria-label="Output GDS name">
      <label><input id="optimize" type="checkbox"> Optimize</label>
      <button type="submit">Run</button>
    </form>
    <div class="grid">
      <section>
        <h2>Status</h2>
        <div id="status">Idle</div>
        <h2>Artifacts</h2>
        <div id="artifacts"></div>
      </section>
      <section>
        <h2>Workbench</h2>
        <iframe id="workbench" title="Generated workbench"></iframe>
      </section>
      <section>
        <h2>Layout</h2>
        <img id="layout" alt="Generated layout screenshot">
      </section>
      <section>
        <h2>JSON</h2>
        <pre id="json"></pre>
      </section>
    </div>
  </main>
  <script>
    const form = document.querySelector('#design-form');
    const statusEl = document.querySelector('#status');
    const artifactsEl = document.querySelector('#artifacts');
    const jsonEl = document.querySelector('#json');
    const workbenchEl = document.querySelector('#workbench');
    const layoutEl = document.querySelector('#layout');

    function fileUrl(path) {
      return 'file:///' + path.replaceAll('\\\\', '/').replace(/^([A-Za-z]):/, '$1:');
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      statusEl.textContent = 'Running local workflow...';
      artifactsEl.textContent = '';
      jsonEl.textContent = '';
      const response = await fetch('/api/design-workflow', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          prompt: document.querySelector('#prompt').value,
          output_name: document.querySelector('#output').value,
          optimize: document.querySelector('#optimize').checked
        })
      });
      const payload = await response.json();
      jsonEl.textContent = JSON.stringify(payload, null, 2);
      if (!response.ok) {
        statusEl.textContent = payload.error || 'Failed';
        return;
      }
      statusEl.textContent = payload.status;
      workbenchEl.src = fileUrl(payload.workbench.html_path);
      layoutEl.src = fileUrl(payload.compile.screenshot_path);
      const links = [
        ['GDS', payload.compile.gds_path],
        ['Layout PNG', payload.compile.screenshot_path],
        ['Workbench', payload.workbench.html_path],
        ['Simulation', payload.simulation.result_path],
        ['Extraction', payload.extraction.result_path]
      ];
      artifactsEl.innerHTML = links.map(([label, path]) => `<p><a href="${fileUrl(path)}">${label}</a></p>`).join('');
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

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send_html(WORKBENCH_APP_HTML)
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
                result = workflow(
                    prompt=str(payload.get("prompt", "Design a 5 Ghz LJPA with wilde bandwidth")),
                    output_name=str(payload.get("output_name", "ljpa_seed.gds")),
                    parameters=payload.get("parameters") if isinstance(payload.get("parameters"), dict) else None,
                    jc_ua_per_um2=float(payload.get("jc_ua_per_um2", 2.0)),
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
