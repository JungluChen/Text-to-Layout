# Public GPT Action Deployment

This document explains how to take the Text-to-Layout API from a **local**
plugin-style server to a **public HTTPS** endpoint that a ChatGPT custom GPT
Action can call.

> **Honest status.** This repository is **local plugin-style ready** and
> **public GPT Action deployable with HTTPS**. No public HTTPS endpoint has been
> deployed or tested here, so the project is **not** claimed to be a "public
> ChatGPT plugin ready" service. The steps below are the documented path to make
> it one.

## The four usage modes

| Mode | Endpoint | Who reaches it | Notes |
| --- | --- | --- | --- |
| Local CLI | none | you | `textlayout generate` / `verify` — no server |
| Local MCP | stdio | a local agent | legacy `text-to-gds` MCP server (`.mcp.json`) |
| Local plugin / API | `http://127.0.0.1:8000` | tools on your machine | `textlayout serve`; OpenAPI at `/openapi.json` |
| Public GPT Action | `https://<your-host>` | ChatGPT (OpenAI servers) | **requires public HTTPS** |

## Why localhost is not enough

A ChatGPT custom GPT Action runs on OpenAI's servers. It **cannot reach
`127.0.0.1` / `localhost`** on your machine. The example manifest
([`../plugin_manifest.example.json`](../plugin_manifest.example.json)) points at
`http://127.0.0.1:8000/openapi.json` for local development only. For a real GPT
Action you must:

1. Deploy the FastAPI app behind a **public HTTPS** URL.
2. Set the OpenAPI `servers[0].url` (and the manifest `api.url`) to that URL.
3. Import the schema into the GPT Action editor.

HTTP (non-TLS) public URLs are rejected by GPT Actions — HTTPS is mandatory.

## Run the server

```bash
textlayout serve --host 0.0.0.0 --port 8000
# or
uvicorn textlayout.backend.app:create_app --factory --host 0.0.0.0 --port 8000
```

Bind to `0.0.0.0` only behind a reverse proxy or platform that terminates TLS.

## Deployment options

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[api]"
EXPOSE 8000
CMD ["uvicorn", "textlayout.backend.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t text-to-layout .
docker run -p 8000:8000 text-to-layout
```

Put a TLS-terminating reverse proxy (Caddy, Nginx, Traefik) in front, or deploy
the image to a platform that provides HTTPS automatically.

### Platform-as-a-service (HTTPS included)

These give you a public `https://…` URL out of the box:

| Platform | Sketch |
| --- | --- |
| **Fly.io** | `fly launch` → `fly deploy`; uses the Dockerfile above |
| **Render** | New Web Service → build `pip install -e ".[api]"`, start with the `uvicorn` command |
| **Railway** | New project from repo → set the start command to the `uvicorn` command |
| **Self-hosted VPS** | Run the container + Caddy/Nginx reverse proxy with a Let's Encrypt cert |

### Development tunnels (NOT for production)

For quick testing only, expose a local server over HTTPS:

```bash
# ngrok
ngrok http 8000          # -> https://<random>.ngrok-free.app

# Cloudflare Tunnel
cloudflared tunnel --url http://localhost:8000
```

Tunnels rotate URLs and have no auth or rate limiting — use them to validate the
GPT Action import, not as a real deployment.

## Update the OpenAPI server URL

FastAPI serves `/openapi.json` with the request's host by default, but pin the
public URL explicitly for GPT Actions. Set it on the app or post-process the
schema:

```python
app = create_app()
app.servers = [{"url": "https://your-host.example.com"}]
```

Then update the manifest:

```json
{
  "api": { "type": "openapi", "url": "https://your-host.example.com/openapi.json" }
}
```

## Test the deployed endpoint

```bash
# Liveness + capability discovery (must be JSON, status "ok")
curl -s https://your-host.example.com/health

# OpenAPI schema (must be valid JSON, openapi "3.x")
curl -s https://your-host.example.com/openapi.json | head -c 200
```

Both endpoints must return `application/json`, never an HTML error page.

## Import into a GPT Action

1. ChatGPT → **Create a GPT** → **Configure** → **Actions** → **Create new action**.
2. **Authentication**: choose to match your deployment (none for a public
   read-only demo; an API key/OAuth proxy for anything writing to disk).
3. **Schema**: paste the contents of `https://your-host.example.com/openapi.json`
   or import by URL.
4. Confirm the operations (`/layout/research`, `/layout/generate`, …) appear, and
   that the server URL is your public HTTPS host.
5. Test in the GPT preview with a small DSL.

## Security checklist before exposing publicly

- Terminate TLS (HTTPS only).
- Add authentication if any endpoint writes to disk (`/layout/generate`,
  `/layout/export`, `/layout/benchmark` write artifacts under the workspace).
- Add rate limiting and a request-size limit at the proxy.
- Run the container as a non-root user with a read-only root filesystem where
  possible; the workspace directory is the only writable path needed.
- Do not expose the legacy `text-to-gds` MCP server publicly — it is a local
  stdio tool, not a hardened web service.
