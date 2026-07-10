"""Phase 8 operational workflows spanning literature, lab, fabrication, signoff, and research."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np


def artifact_hash(value: str | Path | dict[str, Any]) -> str:
    if isinstance(value, dict):
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    else:
        path = Path(value)
        data = path.read_bytes() if path.exists() else str(value).encode()
    return hashlib.sha256(data).hexdigest()


def import_paper_identifier(identifier: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    kind = "doi" if identifier.startswith("10.") else "arxiv" if identifier.lower().startswith("arxiv:") else "unknown"
    return {"schema": "text-to-gds.paper-source.v1", "identifier": identifier, "kind": kind, "metadata": metadata or {}, "status": "imported_metadata" if metadata else "prepared_external_lookup"}


def paper_to_benchmark(source: dict[str, Any], parameters: dict[str, Any], reported: dict[str, float]) -> dict[str, Any]:
    return {"schema": "text-to-gds.paper-benchmark.v1", "source": source, "parameters": parameters, "reported": reported, "required_outputs": ["gds", "drc", "simulation", "comparison"], "source_hash": artifact_hash(source)}


def digitize_plot(image_path: str | Path, *, x_range: tuple[float, float], y_range: tuple[float, float], color_threshold: tuple[int, int, int] = (80, 80, 80)) -> dict[str, Any]:
    from PIL import Image

    rgb = np.asarray(Image.open(image_path).convert("RGB"))
    mask = np.any(rgb < np.asarray(color_threshold), axis=2)
    height, width = mask.shape
    points = []
    for column in range(width):
        rows = np.where(mask[:, column])[0]
        if rows.size:
            x = x_range[0] + column / max(width - 1, 1) * (x_range[1] - x_range[0])
            row = float(np.median(rows))
            y = y_range[1] - row / max(height - 1, 1) * (y_range[1] - y_range[0])
            points.append([x, y])
    return {"schema": "text-to-gds.digitized-plot.v1", "points": points, "image_hash": artifact_hash(image_path), "requires_axis_calibration_review": True}


def paper_reproduction_report(benchmark: dict[str, Any], computed: dict[str, float]) -> dict[str, Any]:
    metrics = {}
    for name, expected in benchmark.get("reported", {}).items():
        actual = computed.get(name)
        metrics[name] = {"reported": expected, "computed": actual, "relative_error": abs(actual - expected) / max(abs(expected), 1e-30) if actual is not None else None}
    valid = [row for row in metrics.values() if row["relative_error"] is not None]
    score = 1.0 - float(np.mean([min(row["relative_error"], 1.0) for row in valid])) if valid else 0.0
    return {"schema": "text-to-gds.reproduction-report.v1", "source": benchmark["source"], "metrics": metrics, "score": score}


def dataset_version(records: list[dict[str, Any]], *, parent: str | None = None) -> dict[str, Any]:
    digest = artifact_hash({"parent": parent, "records": records})
    return {"version_hash": digest, "parent": parent, "record_count": len(records), "process_hashes": sorted({row.get("process_hash") for row in records if row.get("process_hash")}), "measurement_hashes": sorted({row.get("measurement_hash") for row in records if row.get("measurement_hash")})}


def encode_layout_features(polygons: list[dict[str, Any]], ports: list[dict[str, Any]], layers: list[int]) -> dict[str, Any]:
    polygon_features = [[float(item.get("area_um2", 0.0)), float(item.get("perimeter_um", 0.0)), float(item.get("layer", 0))] for item in polygons]
    layer_embedding = {str(layer): [math.sin(layer), math.cos(layer), layer / max(max(layers, default=1), 1)] for layer in layers}
    port_embedding = [[float(port.get("center", [0, 0])[0]), float(port.get("center", [0, 0])[1]), float(port.get("orientation", 0.0)) / 360.0] for port in ports]
    return {"polygon_features": polygon_features, "layer_embedding": layer_embedding, "port_embedding": port_embedding}


def masked_layout_pretraining(tokens: list[int], *, mask_fraction: float = 0.15, seed: int = 42) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    count = max(1, round(len(tokens) * mask_fraction)) if tokens else 0
    indices = sorted(rng.choice(len(tokens), count, replace=False).tolist()) if count else []
    masked = list(tokens)
    labels = {}
    for index in indices:
        labels[index] = masked[index]
        masked[index] = -1
    return {"masked_tokens": masked, "labels": labels, "mask_indices": indices}


def generate_layout_from_embedding(embedding: list[float], *, layer: int = 3) -> dict[str, Any]:
    values = np.asarray(embedding, dtype=float)
    if values.size < 4:
        values = np.pad(values, (0, 4 - values.size))
    width, height = 10.0 + abs(values[0]) * 100.0, 10.0 + abs(values[1]) * 100.0
    gap = 1.0 + abs(values[2]) * 10.0
    return {"schema": "text-to-gds.generated-layout.v1", "layer": [layer, 0], "polygons": [{"bbox_um": [-width / 2, -height / 2, width / 2, height / 2]}], "parameters": {"width_um": width, "height_um": height, "gap_um": gap}, "requires_drc": True}


def cleanroom_workflow(steps: list[dict[str, Any]], completed: set[str] | None = None) -> dict[str, Any]:
    completed = completed or set()
    rows = []
    available = set(completed)
    for step in steps:
        ready = all(requirement in available for requirement in step.get("requires", []))
        status = "complete" if step["name"] in completed else "ready" if ready else "blocked"
        rows.append({**step, "status": status})
        if status == "complete":
            available.add(step["name"])
    return {"steps": rows, "complete": all(row["status"] == "complete" for row in rows)}


def analyze_surface_image(image_path: str | Path, *, pixel_size_nm: float, mode: str) -> dict[str, Any]:
    from PIL import Image

    image = np.asarray(Image.open(image_path).convert("L"), dtype=float)
    gradient_y, gradient_x = np.gradient(image)
    roughness = float(np.std(image)) * pixel_size_nm / 255.0
    return {"mode": mode, "roughness_rms_nm": roughness, "edge_density": float(np.mean(np.hypot(gradient_x, gradient_y) > np.std(image))), "image_hash": artifact_hash(image_path)}


def process_prediction(history: list[dict[str, float]], feature_names: list[str], target: str, query: dict[str, float]) -> dict[str, float]:
    matrix = np.asarray([[1.0] + [row[name] for name in feature_names] for row in history])
    values = np.asarray([row[target] for row in history])
    coefficients = np.linalg.lstsq(matrix, values, rcond=None)[0]
    prediction = float(np.asarray([1.0] + [query[name] for name in feature_names]) @ coefficients)
    residual = values - matrix @ coefficients
    return {"prediction": prediction, "sigma": float(np.std(residual)), "sample_count": len(history)}


def adaptive_measurement(candidates: list[dict[str, Any]], *, uncertainty_weight: float = 1.0) -> dict[str, Any]:
    selected = max(candidates, key=lambda row: float(row.get("expected_information", 0.0)) + uncertainty_weight * float(row.get("uncertainty", 0.0)))
    return {"selected": selected, "candidate_count": len(candidates)}


def select_calibration(measurement: dict[str, Any]) -> dict[str, Any]:
    frequency = float(measurement.get("frequency_ghz", 0.0))
    fixture = measurement.get("fixture", "coax")
    method = "TRL" if fixture in {"on_wafer", "waveguide"} or frequency > 20.0 else "SOLT"
    return {"method": method, "standards_required": ["thru", "reflect", "line"] if method == "TRL" else ["short", "open", "load", "thru"]}


def classify_vna_trace(frequency: list[float], magnitude_db: list[float]) -> dict[str, Any]:
    values = np.asarray(magnitude_db)
    contrast = float(np.max(values) - np.min(values))
    index = int(np.argmin(values))
    label = "resonance_dip" if contrast > 3.0 and 0 < index < len(values) - 1 else "flat_or_failed"
    return {"label": label, "contrast_db": contrast, "feature_frequency": frequency[index]}


def cooldown_memory(database_path: str | Path, run: dict[str, Any]) -> dict[str, Any]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS cooldowns(id INTEGER PRIMARY KEY, payload TEXT NOT NULL, outcome TEXT)")
        cursor = connection.execute("INSERT INTO cooldowns(payload, outcome) VALUES (?, ?)", (json.dumps(run), run.get("outcome")))
    return {"run_id": int(cursor.lastrowid), "database_path": str(path)}


def optimize_heat_load(components: list[dict[str, float]], *, cooling_power_w: float) -> dict[str, Any]:
    total = sum(float(item.get("heat_load_w", 0.0)) for item in components)
    ranked = sorted(components, key=lambda item: item.get("heat_load_w", 0.0), reverse=True)
    return {"total_heat_load_w": total, "margin_w": cooling_power_w - total, "feasible": total <= cooling_power_w, "dominant_loads": ranked[:5]}


def optimize_cable_configuration(candidates: list[dict[str, float]], *, maximum_heat_w: float, maximum_loss_db: float) -> dict[str, Any]:
    feasible = [item for item in candidates if item["heat_load_w"] <= maximum_heat_w and item["loss_db"] <= maximum_loss_db]
    selected = min(feasible, key=lambda item: item["heat_load_w"] + item["loss_db"]) if feasible else None
    return {"selected": selected, "feasible_count": len(feasible)}


def collaboration_workspace(project_id: str, members: list[dict[str, str]], artifacts: list[str]) -> dict[str, Any]:
    return {"schema": "text-to-gds.workspace.v1", "project_id": project_id, "members": members, "artifacts": artifacts, "permissions": {member["user"]: member["role"] for member in members}}


def foundry_handoff(design: dict[str, Any]) -> dict[str, Any]:
    required = ["gds_path", "gds_hash", "process", "drc_report", "lvs_report", "layer_map", "wafer_map"]
    missing = [name for name in required if not design.get(name)]
    return {"schema": "text-to-gds.foundry-handoff.v1", "ready": not missing, "missing": missing, "manifest": {name: design.get(name) for name in required}}


def manufacturing_readiness(evidence: dict[str, Any]) -> dict[str, Any]:
    gates = ["design_verified", "process_compatible", "yield_estimated", "reliability_qualified", "supply_chain_ready", "production_tracking_ready"]
    passed = sum(bool(evidence.get(gate)) for gate in gates)
    return {"level": passed, "maximum_level": len(gates), "passed": passed == len(gates), "missing": [gate for gate in gates if not evidence.get(gate)]}


def compliance_report(evidence: dict[str, Any], standards: list[str]) -> dict[str, Any]:
    checks = {standard: bool(evidence.get(standard)) for standard in standards}
    return {"standards": checks, "compliant": all(checks.values()), "exceptions": [name for name, passed in checks.items() if not passed]}


def mask_order(design: dict[str, Any], *, vendor: str, quantity: int = 1) -> dict[str, Any]:
    return {"schema": "text-to-gds.mask-order.v1", "vendor": vendor, "quantity": quantity, "gds_hash": design.get("gds_hash"), "process": design.get("process"), "status": "prepared_not_submitted", "requires_user_approval": True}


def research_proposal(hypothesis: str, evidence: dict[str, Any], *, kind: str = "experiment") -> dict[str, Any]:
    gaps = [name for name, value in evidence.items() if not value]
    return {"kind": kind, "hypothesis": hypothesis, "specific_aims": ["establish baseline", "test causal mechanism", "validate independently"], "evidence_gaps": gaps, "success_criteria": "pre-registered metrics agree with theory within declared uncertainty"}


def research_critique(result: dict[str, Any]) -> dict[str, Any]:
    required = ["raw_data", "uncertainty", "calibration", "controls", "independent_validation", "limitations"]
    missing = [name for name in required if not result.get(name)]
    return {"weaknesses": [f"Missing {name.replace('_', ' ')}" for name in missing], "missing_experiments": ["replication", "negative control"] if missing else [], "publishable": not missing}


def draft_paper(result: dict[str, Any]) -> dict[str, str]:
    return {"title": result.get("title", "Superconducting quantum device study"), "abstract": result.get("summary", "Results require interpretation."), "methods": json.dumps(result.get("methods", {}), indent=2), "results": json.dumps(result.get("metrics", {}), indent=2), "limitations": json.dumps(result.get("limitations", []))}


def recommend_next_device(results: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    observed = {item.get("topology") for item in results}
    selected = max(candidates, key=lambda item: float(item.get("expected_improvement", 0.0)) + (0.2 if item.get("topology") not in observed else 0.0))
    return {"selected": selected, "reason": "expected improvement plus topology novelty"}
