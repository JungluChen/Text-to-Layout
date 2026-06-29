# OpenAPI Usage

Start the local server:

```bash
textlayout serve --host 127.0.0.1 --port 8000
```

Use `http://127.0.0.1:8000/openapi.json` as the schema URL for a local tool client. No authentication is configured; bind to loopback unless you add an authenticated reverse proxy.

Recommended agent sequence:

1. `GET /health` and select a supported component.
2. `POST /layout/research` with the intended target and initial parameters.
3. Build or revise the Layout DSL from `evidence.proposed_parameters`.
4. `POST /layout/verify` and repair every failing measured check.
5. `POST /layout/simulate?execute=false` to prepare the open-source solver handoff.
6. `POST /layout/generate` or `/layout/benchmark`.
7. Read the final verification, evidence, limitations, and simulation status. Do not describe an analytical value or prepared input as simulated.

Example:

```bash
curl -s -X POST http://127.0.0.1:8000/layout/research \
  -H "Content-Type: application/json" \
  --data-binary @examples/benchmarks/01_idc_0p6pf/layout.json
```

The example manifest at [`../plugin_manifest.example.json`](../plugin_manifest.example.json) points a local tool client to the live OpenAPI document.
