# Tool API Reference

The plugin server exposes a small, AI-callable JSON API. The live OpenAPI schema
is served at `GET /openapi.json` (interactive docs at `/docs`); a snapshot is in
[`openapi.example.json`](openapi.example.json).

Base URL (local): `http://127.0.0.1:8000`

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET`  | `/health` | — | capability discovery: version, components, technologies, formats |
| `POST` | `/layout/generate` | Layout DSL | geometry summary + verification + inline artifacts + written files |
| `POST` | `/layout/verify` | Layout DSL | verification report only (no export) |
| `POST` | `/layout/preview` | Layout DSL | SVG preview string |
| `POST` | `/layout/export?format=gds` | Layout DSL | path + byte size of one written artifact |
| `POST` | `/layout/report` | Layout DSL | summary + verification + files + simulation next steps |

The request body for every `POST` **is the Layout DSL** (`LayoutSpec`), so an
example DSL file can be posted verbatim.

## Input schema (Layout DSL)

```json
{
  "component": "IDC",
  "technology": "generic_2metal",
  "parameters": {
    "finger_pairs": 24, "finger_width_um": 4, "gap_um": 2,
    "overlap_um": 250, "bus_width_um": 25, "metal_layer": "M1"
  },
  "rules":   { "min_width_um": 2, "min_gap_um": 2 },
  "outputs": { "gds": true, "svg": true, "json": true },
  "origin":  [0, 0],
  "metadata": { "intent": "~0.6 pF interdigital capacitor" }
}
```

- `component` — must be a registered generator (`GET /health` → `components`).
- `parameters` — validated against that generator's typed schema; non-physical
  values (negative width, zero gap) are rejected with HTTP 400.
- `rules` — optional design-rule overrides; otherwise the technology defaults apply.
- `outputs` — which artifacts to produce.

## Output schema — `POST /layout/generate`

```json
{
  "status": "pass",
  "component": "IDC",
  "summary": {
    "component": "IDC", "technology": "generic_2metal",
    "layers": ["M1"], "polygon_count": 50, "port_count": 2,
    "bbox_um": {"width": 286.0, "height": 304.0},
    "verification_status": "pass"
  },
  "verification": { "...": "see below" },
  "artifacts": { "json": "{...}", "svg": "<svg ...>" },
  "files": { "gds": ".../idc.gds", "svg": ".../idc.svg", "json": ".../idc.json" }
}
```

## Verification report schema

Returned by `/layout/verify` and embedded in `/generate` and `/report`:

```json
{
  "status": "pass",
  "component": "IDC",
  "checks": [
    { "name": "minimum_gap", "status": "pass", "value_um": 2, "limit_um": 2 },
    { "name": "minimum_width", "status": "pass", "value_um": 4, "limit_um": 2 },
    { "name": "finger_count_sanity", "status": "pass", "value_count": 24 },
    { "name": "ports_exist", "status": "pass", "value_count": 2, "limit_count": 2 }
  ],
  "warnings": [],
  "errors": []
}
```

`status` is `"fail"` if any check failed, else `"pass"`. Each check reports the
value measured and the limit it was tested against. Checks that do not apply to
the component are omitted.

## Errors

Structured JSON, never an HTML stack trace:

```json
{ "error": "InvalidParametersError", "message": "Invalid parameters for component 'IDC': finger_width_um: Input should be greater than 0", "detail": {} }
```

| Error | HTTP | Cause |
|---|---|---|
| `InvalidParametersError` | 400 | parameters fail the generator schema |
| `UnknownComponentError`  | 400 | `component` not registered |
| `UnknownTechnologyError` | 400 | `technology` not in the library |
| `UnknownExporterError`   | 400 | requested format has no exporter |
| `ExportError`            | 500 | exporter failed to write |

## curl examples

```bash
curl -s localhost:8000/health | jq

curl -s -X POST localhost:8000/layout/verify \
  -H 'Content-Type: application/json' \
  -d @examples/idc_0p6pf.json | jq

curl -s -X POST localhost:8000/layout/generate \
  -H 'Content-Type: application/json' \
  -d @examples/idc_0p6pf.json | jq '.status, .files'

curl -s -X POST 'localhost:8000/layout/export?format=gds' \
  -H 'Content-Type: application/json' \
  -d @examples/idc_0p6pf.json | jq
```
