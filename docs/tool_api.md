# Tool API

The FastAPI server exposes structured JSON at `http://127.0.0.1:8000`. Live interactive documentation is at `/docs`; the machine-readable schema is at `/openapi.json`.

## Endpoints

| Method | Path | Result |
| - | - | - |
| GET | `/health` | Version, registered components, technologies, and export formats |
| POST | `/layout/research` | Equations, assumptions, references, estimates, proposed parameters, and simulation plan |
| POST | `/layout/generate` | Evidence, geometry summary, verification, inline text artifacts, and written files |
| POST | `/layout/verify` | Verification report without export |
| POST | `/layout/preview` | Verified SVG preview |
| POST | `/layout/export?format=gds` | One verified artifact path and byte count |
| POST | `/layout/simulate?solver=auto&execute=false` | Prepare or explicitly execute a supported open-source solver |
| POST | `/layout/benchmark` | Complete reproducible artifact/evidence packet |
| POST | `/layout/report` | Evidence, verification, files, and simulation next steps |

Every POST body is a Layout DSL:

```json
{
  "component": "IDC",
  "technology": "generic_2metal",
  "target": {"capacitance_pf": 0.6, "frequency_ghz": 6.0},
  "parameters": {
    "finger_pairs": 22,
    "finger_width_um": 4,
    "gap_um": 2,
    "overlap_um": 250,
    "bus_width_um": 25,
    "metal_layer": "M1"
  },
  "rules": {"min_width_um": 2, "min_gap_um": 2},
  "outputs": {"gds": true, "svg": true, "png": true, "json": true, "report": true}
}
```

`target` is used by research and target comparison. Component parameters are validated by a typed Pydantic model. Unknown fields and non-positive dimensions are rejected.

## Verification and export behavior

Each check contains the check name, status, measured value, limit, unit, and useful failure message when applicable. Warnings do not fail geometry, but they remain visible in the final report.

`/layout/generate` returns failed verification with no final geometry artifacts. `/layout/export`, `/layout/preview`, and `/layout/simulate` return HTTP 422 when verification blocks downstream work. Successful written files include geometry plus Layout DSL provenance, verification JSON, analytical estimate, simulation plan, evidence Markdown, and report Markdown.

`/layout/simulate` defaults to preparation only. For the IDC it returns readiness Level 2 and FastCap-compatible input paths. Set `execute=true` only when a real solver is installed. Missing executables return `status=skipped`; they never create a fake result.

## Errors

Errors are JSON, not HTML:

```json
{
  "error": "InvalidParametersError",
  "message": "Invalid parameters for component 'IDC': finger_width_um must be greater than 0",
  "detail": {}
}
```

Unknown component, technology, exporter, or research model errors return HTTP 400. Verification-blocked single-artifact exports return HTTP 422. Export backend failures return HTTP 500.

## Example

```bash
curl -s -X POST http://127.0.0.1:8000/layout/research \
  -H "Content-Type: application/json" \
  --data-binary @examples/benchmarks/01_idc_0p6pf/layout.json

curl -s -X POST http://127.0.0.1:8000/layout/generate \
  -H "Content-Type: application/json" \
  --data-binary @examples/benchmarks/01_idc_0p6pf/layout.json
```
