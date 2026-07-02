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

## Compile natural language

Compile and inspect the typed DSL without generating files:

```bash
curl -s -X POST http://127.0.0.1:8000/layout/compile \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Create a 50 ohm CPW on silicon"}'
```

Use `/layout/from-text` with the same request shape to run the verified export
workflow. Unsupported, incomplete, or ambiguous prompts return HTTP 400 with
`detail.unresolved_questions`; the compiler does not guess a component.

## Validate the schema

```bash
# Local
curl -s http://127.0.0.1:8000/openapi.json | python -m json.tool > /dev/null && echo "valid JSON"
# /health must be JSON, not an HTML error page
curl -s http://127.0.0.1:8000/health
```

## Public GPT Actions

`http://127.0.0.1:8000` is reachable only on your machine. A ChatGPT custom GPT
Action runs on OpenAI's servers and needs a **public HTTPS** URL. See
[public_gpt_action_deployment.md](public_gpt_action_deployment.md) for Docker /
Fly.io / Render / Railway / VPS deployment, how to pin the OpenAPI `servers` URL,
and how to import the schema into a GPT Action. The project is **local
plugin-style ready** and **public GPT Action deployable with HTTPS** — it is not
a deployed public service.
