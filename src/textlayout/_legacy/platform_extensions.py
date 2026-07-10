"""Cryogenic, AI, data, publication, and platform-level extension functions."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

import numpy as np

BOLTZMANN = 1.380649e-23


CRYOGENIC_CABLES = {
    "stainless_steel_0.085": {"loss_db_per_m_6ghz_300k": 7.0, "thermal_conductivity_w_mk": 16.0},
    "cupronickel_0.085": {"loss_db_per_m_6ghz_300k": 4.5, "thermal_conductivity_w_mk": 22.0},
    "nbti_0.085": {"loss_db_per_m_6ghz_4k": 0.5, "thermal_conductivity_w_mk": 0.3},
}


def cryogenic_cable_database() -> dict[str, dict[str, float]]:
    return {name: dict(values) for name, values in CRYOGENIC_CABLES.items()}


def dilution_refrigerator_model(stages: list[dict[str, float]]) -> dict[str, Any]:
    if not stages:
        raise ValueError("At least one refrigerator stage is required")
    ordered = sorted(stages, key=lambda item: item["temperature_k"], reverse=True)
    for stage in ordered:
        if stage["temperature_k"] <= 0.0 or stage["cooling_power_w"] < 0.0:
            raise ValueError("Invalid refrigerator stage")
    return {"schema": "text-to-gds.dilution-refrigerator.v1", "stages": ordered, "base_temperature_k": ordered[-1]["temperature_k"], "base_cooling_power_w": ordered[-1]["cooling_power_w"]}


def attenuator_thermal_model(*, input_noise_temperature_k: float, physical_temperature_k: float, attenuation_db: float) -> dict[str, float]:
    loss = 10.0 ** (attenuation_db / 10.0)
    output = input_noise_temperature_k / loss + physical_temperature_k * (1.0 - 1.0 / loss)
    return {"output_noise_temperature_k": output, "linear_loss": loss}


def passive_component_noise(*, input_noise_temperature_k: float, physical_temperature_k: float, insertion_loss_db: float) -> dict[str, float]:
    return attenuator_thermal_model(input_noise_temperature_k=input_noise_temperature_k, physical_temperature_k=physical_temperature_k, attenuation_db=insertion_loss_db)


def hemt_amplifier_model(*, gain_db: float, noise_temperature_k: float, p1db_dbm: float) -> dict[str, float]:
    if gain_db < 0.0 or noise_temperature_k < 0.0:
        raise ValueError("HEMT gain and noise must be non-negative")
    return {"gain_db": gain_db, "gain_power": 10.0 ** (gain_db / 10.0), "noise_temperature_k": noise_temperature_k, "p1db_dbm": p1db_dbm}


def friis_noise(stages: list[dict[str, float]]) -> dict[str, Any]:
    total_noise, cumulative_gain = 0.0, 1.0
    terms = []
    for stage in stages:
        gain = 10.0 ** (float(stage["gain_db"]) / 10.0)
        contribution = float(stage.get("noise_temperature_k", 0.0)) / cumulative_gain
        total_noise += contribution
        terms.append({"name": stage.get("name", f"stage_{len(terms)}"), "referred_noise_k": contribution})
        cumulative_gain *= gain
    return {"system_noise_temperature_k": total_noise, "total_gain_db": 10.0 * math.log10(cumulative_gain), "contributions": terms}


def pump_power_budget(*, source_power_dbm: float, path_losses_db: list[float], required_device_power_dbm: float) -> dict[str, float | bool]:
    delivered = source_power_dbm - sum(path_losses_db)
    return {"delivered_power_dbm": delivered, "margin_db": delivered - required_device_power_dbm, "meets_requirement": delivered >= required_device_power_dbm}


def optimize_measurement_chain(candidates: list[list[dict[str, float]]], *, maximum_input_noise_k: float) -> dict[str, Any]:
    evaluated = [(friis_noise(chain), chain) for chain in candidates]
    feasible = [item for item in evaluated if item[0]["system_noise_temperature_k"] <= maximum_input_noise_k]
    result, chain = max(feasible or evaluated, key=lambda item: item[0]["total_gain_db"] - 10.0 * math.log10(max(item[0]["system_noise_temperature_k"], 1e-15)))
    return {"selected_chain": chain, "noise_budget": result, "constraint_met": result["system_noise_temperature_k"] <= maximum_input_noise_k}


def _review(checks: dict[str, bool], domain: str) -> dict[str, Any]:
    failed = [name for name, passed in checks.items() if not passed]
    return {"schema": f"text-to-gds.ai-{domain}-review.v1", "passed": not failed, "checks": checks, "findings": failed, "score": sum(checks.values()) / max(len(checks), 1)}


def ai_design_reviewer(design: dict[str, Any]) -> dict[str, Any]:
    return _review({"target_frequency": float(design.get("target_frequency_ghz", 0.0)) > 0.0, "layout_selected": bool(design.get("pcell") or design.get("layout")), "process_selected": bool(design.get("process_id") or design.get("process_stack")), "simulation_plan": bool(design.get("simulation") or design.get("simulator"))}, "design")


def ai_physics_checker(result: dict[str, Any]) -> dict[str, Any]:
    return _review({"finite_values": all(np.isfinite(value) for value in _numeric_values(result)), "positive_frequency": all(value > 0.0 for key, value in _numeric_items(result) if "frequency" in key), "validity_declared": bool(result.get("model_validity") or result.get("validity") or result.get("source"))}, "physics")


def ai_fabrication_checker(design: dict[str, Any]) -> dict[str, Any]:
    return _review({"drc_passed": design.get("drc_passed") is True or design.get("drc", {}).get("passed") is True, "pdk_versioned": bool(re.search(r"@\d+\.\d+\.\d+", str(design.get("process", "")))), "yield_estimated": design.get("yield_fraction") is not None, "provenance_present": bool(design.get("provenance"))}, "fabrication")


def ai_measurement_assistant(measurement: dict[str, Any]) -> dict[str, Any]:
    return _review({"calibrated": measurement.get("calibrated") is True, "power_limits": bool(measurement.get("power_limits")), "raw_data_preserved": bool(measurement.get("raw_data_path")), "uncertainty_reported": measurement.get("uncertainty") is not None}, "measurement")


def _numeric_items(value: Any, prefix: str = "") -> list[tuple[str, float]]:
    output = []
    if isinstance(value, dict):
        for key, item in value.items():
            output.extend(_numeric_items(item, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        output.append((prefix, float(value)))
    return output


def _numeric_values(value: Any) -> list[float]:
    return [number for _, number in _numeric_items(value)]


def multi_agent_workflow(state: dict[str, Any]) -> dict[str, Any]:
    """Deterministic local orchestration contract for layout/EM/physics/experiment roles."""
    stages = [
        {"agent": "layout", "requires": ["prompt"], "produces": ["gds", "sidecar", "drc"]},
        {"agent": "em", "requires": ["gds", "sidecar"], "produces": ["s_parameters", "field_energy"]},
        {"agent": "physics", "requires": ["s_parameters", "field_energy"], "produces": ["circuit", "quantum_metrics"]},
        {"agent": "experiment", "requires": ["quantum_metrics"], "produces": ["measurement_plan", "feedback"]},
    ]
    available = set(state)
    for stage in stages:
        stage["ready"] = all(item in available for item in stage["requires"])
        if stage["ready"]:
            available.update(stage["produces"])
    return {"schema": "text-to-gds.multi-agent-workflow.v1", "stages": stages}


def autonomous_design_iteration(parameters: dict[str, float], measured: dict[str, float], targets: dict[str, float], sensitivities: dict[str, dict[str, float]], *, step_limit_fraction: float = 0.2) -> dict[str, Any]:
    names = list(parameters)
    metrics = [name for name in targets if name in measured]
    jacobian = np.asarray([[sensitivities.get(metric, {}).get(name, 0.0) for name in names] for metric in metrics])
    error = np.asarray([targets[name] - measured[name] for name in metrics])
    delta = np.linalg.pinv(jacobian) @ error if jacobian.size else np.zeros(len(names))
    next_parameters = {name: value + float(np.clip(change, -abs(value) * step_limit_fraction, abs(value) * step_limit_fraction)) for name, value, change in zip(names, parameters.values(), delta, strict=True)}
    return {"parameters": parameters, "errors": dict(zip(metrics, error.tolist(), strict=True)), "next_parameters": next_parameters}


def reinforcement_learning_optimizer(actions: list[dict[str, float]], rewards: list[float], *, exploration: float = 0.1) -> dict[str, Any]:
    if len(actions) != len(rewards) or not actions:
        raise ValueError("Actions and rewards must have equal non-zero length")
    best = int(np.argmax(rewards))
    probabilities = np.full(len(actions), exploration / len(actions))
    probabilities[best] += 1.0 - exploration
    return {"selected_action": actions[best], "action_probabilities": probabilities.tolist(), "method": "epsilon-greedy replay policy"}


def bayesian_design_prediction(previous: list[dict[str, Any]], query: dict[str, float], *, metric: str, length_scale: float = 1.0) -> dict[str, float]:
    if not previous:
        raise ValueError("Previous chip records are required")
    keys = sorted(query)
    distances = np.asarray([sum(((float(record["parameters"][key]) - query[key]) / length_scale) ** 2 for key in keys) for record in previous])
    weights = np.exp(-0.5 * distances)
    values = np.asarray([float(record["metrics"][metric]) for record in previous])
    weights /= max(float(np.sum(weights)), 1e-30)
    mean = float(weights @ values)
    variance = float(weights @ (values - mean) ** 2)
    return {"mean": mean, "standard_deviation": math.sqrt(variance), "effective_samples": float(1.0 / np.sum(weights**2))}


def failure_analysis(evidence: dict[str, Any]) -> dict[str, Any]:
    rules = [
        ("drc", evidence.get("drc_passed") is False, "layout rule violation"),
        ("em", evidence.get("em_converged") is False, "unconverged EM model"),
        ("fabrication", float(evidence.get("yield_fraction", 1.0)) < 0.5, "low predicted fabrication yield"),
        ("measurement", evidence.get("calibrated") is False, "uncalibrated measurement chain"),
    ]
    causes = [{"domain": domain, "cause": cause} for domain, triggered, cause in rules if triggered]
    return {"causes": causes, "status": "failure_explained" if causes else "insufficient_evidence"}


def compare_with_paper(result: dict[str, float], reported: dict[str, float], tolerances: dict[str, float]) -> dict[str, Any]:
    rows = {}
    for key in sorted(set(result) & set(reported)):
        relative = abs(result[key] - reported[key]) / max(abs(reported[key]), 1e-30)
        rows[key] = {"computed": result[key], "reported": reported[key], "relative_error": relative, "passed": relative <= tolerances.get(key, 0.05)}
    return {"passed": bool(rows) and all(row["passed"] for row in rows.values()), "metrics": rows}


def extract_literature_parameters(text: str) -> dict[str, Any]:
    patterns = {"frequency_ghz": r"(\d+(?:\.\d+)?)\s*GHz", "gain_db": r"(\d+(?:\.\d+)?)\s*dB\s*gain", "bandwidth_mhz": r"(\d+(?:\.\d+)?)\s*MHz\s*(?:bandwidth|BW)", "noise_photons": r"(\d+(?:\.\d+)?)\s*(?:added\s*)?photons?"}
    extracted = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        extracted[key] = float(match.group(1)) if match else None
    return {"parameters": extracted, "source": "provided_text", "requires_manual_verification": True}


def initialize_knowledge_database(path: str | Path) -> Path:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS records (
          id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, record_key TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP, text TEXT NOT NULL, payload_json TEXT NOT NULL,
          vector_json TEXT, UNIQUE(kind, record_key));
        CREATE INDEX IF NOT EXISTS idx_records_kind ON records(kind);
        """)
    return database


def index_record(path: str | Path, *, kind: str, record_key: str, payload: dict[str, Any], text: str = "", vector: list[float] | None = None) -> dict[str, Any]:
    database = initialize_knowledge_database(path)
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT OR REPLACE INTO records(kind, record_key, text, payload_json, vector_json) VALUES (?, ?, ?, ?, ?)", (kind, record_key, text, json.dumps(payload), json.dumps(vector) if vector is not None else None))
    return {"database_path": str(database), "kind": kind, "record_key": record_key}


def search_records(path: str | Path, query: str, *, kind: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    sql = "SELECT kind, record_key, payload_json FROM records WHERE (text LIKE ? OR payload_json LIKE ?)"
    parameters: list[Any] = [f"%{query}%", f"%{query}%"]
    if kind:
        sql += " AND kind=?"
        parameters.append(kind)
    sql += " ORDER BY id DESC LIMIT ?"
    parameters.append(limit)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [{"kind": row[0], "record_key": row[1], "payload": json.loads(row[2])} for row in rows]


def similarity_search(path: str | Path, vector: list[float], *, kind: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    sql = "SELECT kind, record_key, payload_json, vector_json FROM records WHERE vector_json IS NOT NULL"
    parameters: list[Any] = []
    if kind:
        sql += " AND kind=?"
        parameters.append(kind)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    query = np.asarray(vector, dtype=float)
    scored = []
    for row in rows:
        candidate = np.asarray(json.loads(row[3]), dtype=float)
        if candidate.shape != query.shape:
            continue
        score = float(query @ candidate / max(np.linalg.norm(query) * np.linalg.norm(candidate), 1e-30))
        scored.append({"kind": row[0], "record_key": row[1], "payload": json.loads(row[2]), "similarity": score})
    return sorted(scored, key=lambda item: item["similarity"], reverse=True)[:limit]


def figure_style(style: str) -> dict[str, Any]:
    styles = {
        "nature": {"width_in": 3.5, "font": "Arial", "font_size": 7, "dpi": 600},
        "ieee_tas": {"width_in": 3.5, "font": "Times New Roman", "font_size": 8, "dpi": 600},
        "prx": {"width_in": 3.375, "font": "Computer Modern", "font_size": 8, "dpi": 600},
    }
    if style.lower() not in styles:
        raise ValueError(f"Unknown figure style {style!r}")
    return styles[style.lower()]


def generate_caption(figure: dict[str, Any]) -> str:
    panels = figure.get("panels", [])
    descriptions = [f"({chr(97 + index)}) {panel.get('description', panel.get('title', 'Result'))}" for index, panel in enumerate(panels)]
    return f"Figure {figure.get('number', '?')}. " + " ".join(descriptions)


def device_comparison_table(devices: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    return {"columns": ["device"] + fields, "rows": [{"device": device.get("name", device.get("id", "unknown")), **{field: device.get(field) for field in fields}} for device in devices]}


def doi_benchmark_record(*, doi: str, title: str, parameters: dict[str, Any], citations: list[str] | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        raise ValueError("Invalid DOI format")
    return {"schema": "text-to-gds.doi-benchmark.v1", "doi": doi, "title": title, "parameters": parameters, "citations": citations or []}


def citation_graph(records: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [{"id": record["doi"], "title": record.get("title", "")} for record in records]
    known = {node["id"] for node in nodes}
    edges = [{"source": record["doi"], "target": cited} for record in records for cited in record.get("citations", []) if cited in known]
    return {"nodes": nodes, "edges": edges}


def plugin_manifest(name: str, module: str, capabilities: list[str]) -> dict[str, Any]:
    return {"schema": "text-to-gds.plugin.v1", "name": name, "module": module, "capabilities": capabilities, "isolation": "local_process"}


def docker_environment() -> str:
    return """FROM python:3.12-slim\nWORKDIR /app\nCOPY pyproject.toml uv.lock ./\nRUN pip install uv && uv sync --frozen --no-dev\nCOPY . .\nCMD [\"uv\", \"run\", \"text-to-gds\"]\n"""


def cloud_worker_job(adapter: str, artifacts: list[str], parameters: dict[str, Any]) -> dict[str, Any]:
    """Create a provider-neutral job envelope; submission remains an external adapter action."""
    return {"schema": "text-to-gds.remote-worker-job.v1", "adapter": adapter, "artifacts": artifacts, "parameters": parameters, "status": "prepared", "core_dependency": False}


def rest_api_spec() -> dict[str, Any]:
    return {"openapi": "3.1.0", "info": {"title": "Text-to-GDS local API", "version": "1.0.0"}, "paths": {"/designs": {"post": {"summary": "Create a local design workflow"}}, "/jobs/{job_id}": {"get": {"summary": "Read local job status"}}, "/artifacts/{name}": {"get": {"summary": "Read an artifact"}}}}


def authorize(role: str, action: str) -> bool:
    permissions = {"viewer": {"read"}, "designer": {"read", "design", "simulate"}, "fabrication": {"read", "design", "simulate", "release"}, "admin": {"read", "design", "simulate", "release", "manage"}}
    return action in permissions.get(role, set())


def collaborative_workspace_event(*, actor: str, action: str, artifact: str, revision: str) -> dict[str, str]:
    return {"actor": actor, "action": action, "artifact": artifact, "revision": revision}


def ci_pipeline() -> str:
    return """name: text-to-gds\non: [push, pull_request]\njobs:\n  test:\n    runs-on: windows-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: astral-sh/setup-uv@v5\n      - run: uv sync --dev\n      - run: uv run ruff check .\n      - run: uv run pytest\n"""


def regression_test_case(name: str, inputs: dict[str, Any], expected: dict[str, Any], tolerance: float = 1e-6) -> dict[str, Any]:
    return {"name": name, "inputs": inputs, "expected": expected, "relative_tolerance": tolerance}


def benchmark_test_case(device: str, targets: dict[str, float], evidence: list[str]) -> dict[str, Any]:
    return {"schema": "text-to-gds.device-benchmark.v1", "device": device, "targets": targets, "required_evidence": evidence}


def generate_api_documentation(functions: list[Callable[..., Any]]) -> str:
    lines = ["# Generated API Reference", ""]
    for function in functions:
        lines.extend([f"## `{function.__name__}`", "", (function.__doc__ or "No description.").strip(), ""])
    return "\n".join(lines)


def example_gallery(examples: list[dict[str, str]]) -> str:
    return "# Example Gallery\n\n" + "\n\n".join(f"## {item['title']}\n\n![{item['title']}]({item['image']})\n\n{item.get('description', '')}" for item in examples)


def tutorial_notebook(title: str, steps: list[dict[str, str]]) -> dict[str, Any]:
    cells = [{"cell_type": "markdown", "metadata": {}, "source": [f"# {title}\n"]}]
    for step in steps:
        cells.append({"cell_type": "markdown", "metadata": {}, "source": [step.get("markdown", "")]})
        if step.get("code"):
            cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [step["code"]]})
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 5}


def closed_loop_platform(prompt: str, callbacks: dict[str, Callable[[Any], Any]]) -> dict[str, Any]:
    """Execute the complete local closed loop through explicitly supplied adapters."""
    stages = ["design", "gds", "drc", "em", "quantum", "optimization", "fabrication", "measurement", "redesign"]
    state: Any = {"prompt": prompt}
    history = []
    for stage in stages:
        callback = callbacks.get(stage)
        if callback is None:
            history.append({"stage": stage, "status": "prepared_external_adapter" if stage in {"fabrication", "measurement"} else "missing_callback"})
            continue
        state = callback(state)
        history.append({"stage": stage, "status": "completed"})
    return {"schema": "text-to-gds.closed-loop-platform.v1", "history": history, "state": state}
