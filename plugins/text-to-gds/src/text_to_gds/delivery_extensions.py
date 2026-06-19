"""Data exports, publication artifacts, deployment manifests, SDKs, and collaboration helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any


def ml_ready_device_record(device: dict[str, Any], *, features: list[str], targets: list[str]) -> dict[str, Any]:
    missing = [name for name in features + targets if name not in device]
    return {"id": device.get("id"), "features": {name: device.get(name) for name in features}, "targets": {name: device.get(name) for name in targets}, "missing": missing, "training_eligible": not missing, "provenance": device.get("provenance")}


def circuit_graph_database_record(circuit: dict[str, Any]) -> dict[str, Any]:
    nodes = [{"id": node, "kind": "net"} for node in circuit.get("nodes", [])]
    edges = []
    for element in circuit.get("elements", []):
        element_id = element["name"]
        nodes.append({"id": element_id, "kind": element.get("kind", "device"), "parameters": element.get("parameters", {})})
        edges.extend({"source": element_id, "target": net, "relationship": "CONNECTED_TO"} for net in element.get("nodes", []))
    return {"schema": "text-to-gds.circuit-property-graph.v1", "nodes": nodes, "edges": edges}


def failed_experiment_record(experiment: dict[str, Any], failure: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "text-to-gds.failed-experiment.v1", "experiment": experiment, "failure": failure, "search_tags": sorted(set(experiment.get("tags", []) + failure.get("domains", []))), "reusable_negative_result": bool(failure.get("root_cause"))}


def extract_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema": payload.get("schema"), "device_id": payload.get("device_id", payload.get("id")), "process_id": payload.get("process_id"), "created_at": payload.get("created_at"), "software_versions": payload.get("software_versions", {}), "source_files": payload.get("source_files", []), "units_declared": payload.get("units") is not None, "provenance_present": payload.get("provenance") is not None}


def fair_data_export(dataset: dict[str, Any], *, license_name: str, persistent_id: str | None = None) -> dict[str, Any]:
    metadata = extract_metadata(dataset)
    return {"schema": "text-to-gds.fair-export.v1", "findable": bool(persistent_id and metadata.get("device_id")), "accessible": bool(license_name), "interoperable": bool(dataset.get("schema") and dataset.get("units")), "reusable": bool(metadata["provenance_present"] and license_name), "persistent_id": persistent_id, "license": license_name, "metadata": metadata, "data": dataset}


def doi_dataset(*, title: str, creators: list[dict[str, str]], description: str, files: list[dict[str, Any]], related_identifiers: list[str] | None = None) -> dict[str, Any]:
    return {"metadata": {"title": title, "creators": creators, "description": description, "upload_type": "dataset", "related_identifiers": related_identifiers or []}, "files": files, "status": "ready_for_repository_deposition", "doi": None}


def latex_paper(*, title: str, authors: list[str], abstract: str, sections: list[dict[str, str]], template: str = "generic") -> str:
    template_class = {"generic": "article", "nature": "article", "ieee_tas": "IEEEtran"}.get(template)
    if template_class is None:
        raise ValueError("Unknown LaTeX template")
    body = "\n".join(f"\\section{{{section['title']}}}\n{section['body']}" for section in sections)
    author_line = " \\and ".join(authors)
    return f"""\\documentclass{{{template_class}}}
\\usepackage{{graphicx,amsmath,booktabs,siunitx}}
\\title{{{title}}}
\\author{{{author_line}}}
\\begin{{document}}
\\maketitle
\\begin{{abstract}}{abstract}\\end{{abstract}}
{body}
\\end{{document}}
"""


def overleaf_export(main_tex: str, figures: list[str], bibliography: str | None = None) -> dict[str, str]:
    files = {"main.tex": main_tex}
    if bibliography is not None:
        files["references.bib"] = bibliography
    files["figures/README.txt"] = "Include these local figure files:\n" + "\n".join(figures)
    return files


def publication_template(style: str) -> dict[str, Any]:
    templates = {
        "nature": {"document_class": "article", "columns": 1, "figure_width_mm": 89, "citation_style": "naturemag"},
        "ieee_tas": {"document_class": "IEEEtran", "columns": 2, "figure_width_mm": 88.9, "citation_style": "IEEEtran"},
    }
    if style not in templates:
        raise ValueError("Unknown publication template")
    return templates[style]


def beautify_figure(specification: dict[str, Any], *, style: str = "nature") -> dict[str, Any]:
    from text_to_gds.platform_extensions import figure_style

    styled = dict(specification)
    styled["style"] = figure_style(style)
    styled["accessibility"] = {"colorblind_safe": True, "minimum_font_pt": styled["style"]["font_size"], "vector_text": True}
    styled["cleanup"] = ["remove chart junk", "use SI units", "label panels", "declare uncertainty", "preserve raw data"]
    return styled


def supplementary_information(methods: list[dict[str, str]], datasets: list[dict[str, Any]], equations: list[str]) -> str:
    method_text = "\n".join(f"\\subsection{{{item['title']}}}\n{item['body']}" for item in methods)
    data_text = "\n".join(f"\\item {item.get('name', 'Dataset')}: {item.get('description', '')}" for item in datasets)
    equation_text = "\n".join(f"\\begin{{equation}}{equation}\\end{{equation}}" for equation in equations)
    return f"\\section{{Supplementary Methods}}\n{method_text}\n\\section{{Data}}\n\\begin{{itemize}}{data_text}\\end{{itemize}}\n\\section{{Equations}}\n{equation_text}"


def benchmark_comparison_table(results: list[dict[str, Any]], metrics: list[str]) -> dict[str, Any]:
    return {"columns": ["device", "source"] + metrics, "rows": [{"device": row.get("device"), "source": row.get("source"), **{metric: row.get(metric) for metric in metrics}} for row in results]}


def reviewer_response(comments: list[dict[str, str]], changes: dict[str, str]) -> str:
    blocks = []
    for index, comment in enumerate(comments, 1):
        identifier = comment.get("id", str(index))
        blocks.append(f"## Comment {identifier}\n\n> {comment['text']}\n\n**Response:** {changes.get(identifier, 'Response required.')}\n")
    return "# Response to Reviewers\n\n" + "\n".join(blocks)


def kubernetes_worker_manifest(*, image: str, queue_name: str, cpu: str = "4", memory: str = "16Gi", gpu: int = 0) -> dict[str, Any]:
    limits: dict[str, Any] = {"cpu": cpu, "memory": memory}
    if gpu:
        limits["nvidia.com/gpu"] = gpu
    return {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "text-to-gds-worker"}, "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "text-to-gds-worker"}}, "template": {"metadata": {"labels": {"app": "text-to-gds-worker"}}, "spec": {"containers": [{"name": "worker", "image": image, "env": [{"name": "QUEUE_NAME", "value": queue_name}], "resources": {"limits": limits}}]}}}}


def hpc_job_script(*, command: str, job_name: str = "text-to-gds", nodes: int = 1, cores: int = 16, walltime: str = "04:00:00", gpu: int = 0) -> str:
    gpu_line = f"#SBATCH --gres=gpu:{gpu}\n" if gpu else ""
    return f"#!/bin/bash\n#SBATCH --job-name={job_name}\n#SBATCH --nodes={nodes}\n#SBATCH --ntasks-per-node={cores}\n#SBATCH --time={walltime}\n{gpu_line}set -euo pipefail\n{command}\n"


def initialize_job_queue(path: str | Path) -> Path:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, priority INTEGER NOT NULL, status TEXT NOT NULL, payload_json TEXT NOT NULL, result_json TEXT)")
    return database


def enqueue_job(path: str | Path, *, kind: str, payload: dict[str, Any], priority: int = 0) -> dict[str, Any]:
    database = initialize_job_queue(path)
    with sqlite3.connect(database) as connection:
        cursor = connection.execute("INSERT INTO jobs(kind, priority, status, payload_json) VALUES (?, ?, 'queued', ?)", (kind, priority, json.dumps(payload)))
        job_id = int(cursor.lastrowid)
    return {"job_id": job_id, "status": "queued", "database_path": str(database)}


def claim_job(path: str | Path, *, kinds: list[str] | None = None) -> dict[str, Any] | None:
    database = initialize_job_queue(path)
    with sqlite3.connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        sql = "SELECT id, kind, payload_json FROM jobs WHERE status='queued'"
        parameters: list[Any] = []
        if kinds:
            sql += f" AND kind IN ({','.join('?' for _ in kinds)})"
            parameters.extend(kinds)
        sql += " ORDER BY priority DESC, id ASC LIMIT 1"
        row = connection.execute(sql, parameters).fetchone()
        if row:
            connection.execute("UPDATE jobs SET status='running' WHERE id=?", (row[0],))
    return {"job_id": row[0], "kind": row[1], "payload": json.loads(row[2])} if row else None


def database_backend(url: str) -> dict[str, Any]:
    if url.startswith("sqlite:///"):
        return {"driver": "sqlite", "path": url.removeprefix("sqlite:///"), "local": True}
    if url.startswith(("postgresql://", "postgres://")):
        return {"driver": "postgresql", "url": url, "local": False, "adapter_required": "psycopg"}
    raise ValueError("Only SQLite and PostgreSQL URLs are supported")


def create_password_record(password: str, *, iterations: int = 200000) -> dict[str, Any]:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return {"algorithm": "pbkdf2_sha256", "iterations": iterations, "salt_hex": salt.hex(), "digest_hex": digest.hex()}


def verify_password(password: str, record: dict[str, Any]) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(record["salt_hex"]), int(record["iterations"]))
    return hmac.compare_digest(digest.hex(), record["digest_hex"])


def collaborative_edit(document: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
    result = document
    offset = 0
    applied = []
    for operation in sorted(operations, key=lambda item: (int(item["position"]), item.get("actor", ""))):
        position = int(operation["position"]) + offset
        if operation["type"] == "insert":
            text = str(operation["text"])
            result = result[:position] + text + result[position:]
            offset += len(text)
        elif operation["type"] == "delete":
            length = int(operation["length"])
            result = result[:position] + result[position + length :]
            offset -= length
        else:
            raise ValueError("Unknown edit operation")
        applied.append(operation)
    return {"document": result, "operations": applied, "revision": hashlib.sha256(result.encode()).hexdigest()}


def python_sdk_source() -> str:
    return '''from __future__ import annotations
import json
from urllib.request import Request, urlopen

class TextToGDSClient:
    def __init__(self, base_url="http://127.0.0.1:8765", token=None):
        self.base_url, self.token = base_url.rstrip("/"), token
    def request(self, method, path, payload=None):
        headers = {"Content-Type": "application/json"}
        if self.token: headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.base_url + path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
        with urlopen(request) as response: return json.load(response)
'''


def julia_sdk_source() -> str:
    return '''module TextToGDS
using HTTP, JSON3
export Client, request
struct Client
    base_url::String
    token::Union{String,Nothing}
end
function request(client::Client, method::String, path::String; payload=nothing)
    headers = ["Content-Type" => "application/json"]
    client.token !== nothing && push!(headers, "Authorization" => "Bearer $(client.token)")
    response = HTTP.request(method, client.base_url * path, headers, payload === nothing ? UInt8[] : JSON3.write(payload))
    JSON3.read(response.body)
end
end
'''


def vscode_extension_manifest() -> dict[str, Any]:
    return {"name": "text-to-gds", "displayName": "Text-to-GDS", "version": "0.1.0", "engines": {"vscode": "^1.90.0"}, "activationEvents": ["onCommand:text-to-gds.plan", "onCommand:text-to-gds.compile"], "contributes": {"commands": [{"command": "text-to-gds.plan", "title": "Text-to-GDS: Plan Device"}, {"command": "text-to-gds.compile", "title": "Text-to-GDS: Compile Layout"}]}, "main": "./extension.js"}


def cli_assistant_commands() -> dict[str, Any]:
    return {"commands": {"plan": {"arguments": ["prompt"]}, "compile": {"arguments": ["pcell", "parameters"]}, "drc": {"arguments": ["gds"]}, "simulate": {"arguments": ["sidecar", "solver"]}, "registry": {"arguments": ["list"]}}, "transport": "local_mcp_or_python"}


def continuous_benchmark_pipeline(devices: list[str]) -> dict[str, Any]:
    return {"schedule": "0 3 * * 1", "matrix": {"device": devices}, "steps": ["install toolchain", "compile reference GDS", "run DRC", "run available simulations", "compare metrics", "upload evidence"], "failure_policy": "fail on regression; skip unavailable licensed backends explicitly"}
