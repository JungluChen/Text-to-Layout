"""Local plugin marketplace, project templates, foundry import, and fabrication operations."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from text_to_gds.pdk import SuperconductingPDK, load_pdk


class PCellMarketplace:
    """Filesystem marketplace for reviewed local PCell plugin manifests."""

    def __init__(self, roots: list[str | Path]):
        self.roots = [Path(root) for root in roots]

    def list(self) -> list[dict[str, Any]]:
        entries = []
        for root in self.roots:
            for path in sorted(root.glob("**/pcell-plugin.yaml")):
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict) or payload.get("schema") != "text-to-gds.pcell-plugin.v1":
                    continue
                entries.append({**payload, "manifest_path": str(path)})
        return entries

    def install(self, plugin_id: str, destination: str | Path) -> dict[str, Any]:
        if Path(plugin_id).name != plugin_id or plugin_id in {".", ".."}:
            raise ValueError("Plugin ID must be a safe single path segment")
        matches = [entry for entry in self.list() if entry.get("id") == plugin_id]
        if not matches:
            raise KeyError(f"Unknown PCell plugin {plugin_id!r}")
        manifest = Path(matches[0]["manifest_path"])
        target = Path(destination) / plugin_id
        if target.exists():
            raise FileExistsError(f"Plugin is already installed: {target}")
        shutil.copytree(manifest.parent, target)
        return {"plugin_id": plugin_id, "installed_path": str(target), "status": "installed"}


def community_device_library() -> dict[str, Any]:
    from text_to_gds.layout_automation import quantum_cell_library

    return {"schema": "text-to-gds.community-device-library.v1", "devices": quantum_cell_library(), "source": "built_in_reviewed_cells"}


def generate_experiment_notebook(title: str, experiment: dict[str, Any]) -> dict[str, Any]:
    from text_to_gds.platform_extensions import tutorial_notebook

    steps = [
        {"markdown": "## Configuration", "code": f"experiment = {experiment!r}\nexperiment"},
        {"markdown": "## Instrument discovery", "code": "# Bind approved QCoDeS/SCPI instruments here. Keep RF outputs disabled."},
        {"markdown": "## Calibration", "code": "calibration = {'status': 'required'}\ncalibration"},
        {"markdown": "## Acquisition", "code": "# Execute the approved measurement recipe and preserve raw data."},
        {"markdown": "## Analysis", "code": "# Fit resonance, gain, bandwidth, noise, and uncertainty."},
    ]
    return tutorial_notebook(title, steps)


def generate_project_template(kind: str, *, name: str) -> dict[str, str]:
    kinds = {
        "jpa": "lumped_element_jpa_seed",
        "qubit": "transmon_island",
        "resonator": "cpw_straight",
        "sfq": "dc_squid_pair",
    }
    if kind not in kinds:
        raise ValueError(f"Unknown project kind {kind!r}")
    files = {
        "project.yaml": yaml.safe_dump({"schema": "text-to-gds.project.v1", "name": name, "kind": kind, "pcell": kinds[kind], "process": "custom_process@0.1.0"}, sort_keys=False),
        "design.py": f"from text_to_gds.pcells import {kinds[kind]}\n\ncomponent = {kinds[kind]}()\n",
        "README.md": f"# {name}\n\nLocal Text-to-GDS {kind.upper()} project.\n",
    }
    return files


def import_foundry_pdk(path: str | Path, *, layer_map: dict[str, str] | None = None) -> SuperconductingPDK:
    """Import native Text-to-GDS YAML or normalize a foundry mapping through explicit field names."""
    try:
        return load_pdk(path)
    except ValueError:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        mapping = layer_map or {}
        normalized_layers = {}
        for source_name, layer in payload.get("layers", {}).items():
            name = mapping.get(source_name, source_name)
            normalized_layers[name] = {
                "gds": layer.get("gds", [layer.get("layer"), layer.get("datatype", 0)]),
                "purpose": layer.get("purpose", name),
                "material": layer["material"],
                "thickness_nm": layer["thickness_nm"],
                "min_width_um": layer["min_width_um"],
                "min_spacing_um": layer["min_spacing_um"],
                "overlay_tolerance_um": layer.get("overlay_tolerance_um", payload["constraints"]["overlay_tolerance_um"]),
                **({"critical_current_density_ua_per_um2": layer["critical_current_density_ua_per_um2"]} if "critical_current_density_ua_per_um2" in layer else {}),
            }
        normalized = {
            "schema": "text-to-gds.superconducting-pdk.v1",
            "process_id": payload["process_id"],
            "name": payload["name"],
            "version": payload["version"],
            "status": payload.get("status", "imported"),
            "materials": payload["materials"],
            "layers": normalized_layers,
            "constraints": payload["constraints"],
            "provenance": {**payload.get("provenance", {}), "imported_from": str(path)},
        }
        return SuperconductingPDK.from_dict(normalized, source_path=path)


def migrate_process_geometry(parameters: dict[str, float], source: SuperconductingPDK, target: SuperconductingPDK) -> dict[str, Any]:
    """Scale geometry to target rules and report every forced migration change."""
    migrated = dict(parameters)
    changes = {}
    width_keys = [key for key in parameters if "width" in key]
    spacing_keys = [key for key in parameters if "gap" in key or "spacing" in key]
    for key in width_keys:
        minimum = target.constraints.min_trace_width_um
        if "junction" in key:
            minimum = target.constraints.min_junction_width_um
        if migrated[key] < minimum:
            changes[key] = {"before": migrated[key], "after": minimum, "reason": "target minimum width"}
            migrated[key] = minimum
    for key in spacing_keys:
        minimum = target.constraints.min_trace_spacing_um
        if migrated[key] < minimum:
            changes[key] = {"before": migrated[key], "after": minimum, "reason": "target minimum spacing"}
            migrated[key] = minimum
    source_jc = next((layer.critical_current_density_ua_per_um2 for layer in source.layers.values() if layer.critical_current_density_ua_per_um2), None)
    target_jc = next((layer.critical_current_density_ua_per_um2 for layer in target.layers.values() if layer.critical_current_density_ua_per_um2), None)
    if source_jc and target_jc and "junction_area_um2" in migrated:
        before = migrated["junction_area_um2"]
        migrated["junction_area_um2"] *= source_jc / target_jc
        changes["junction_area_um2"] = {"before": before, "after": migrated["junction_area_um2"], "reason": "preserve critical current"}
    return {"source": f"{source.process_id}@{source.version}", "target": f"{target.process_id}@{target.version}", "parameters": migrated, "changes": changes, "requires_drc_and_em_revalidation": True}


def estimate_fabrication_cost(*, wafer_count: int, mask_count: int, wafer_cost: float, mask_cost: float, setup_cost: float = 0.0, expected_yield: float = 1.0, chips_per_wafer: int = 1) -> dict[str, float]:
    if wafer_count < 1 or mask_count < 1 or min(wafer_cost, mask_cost, chips_per_wafer, expected_yield) <= 0.0:
        raise ValueError("Invalid fabrication cost inputs")
    total = setup_cost + wafer_count * wafer_cost + mask_count * mask_cost
    good_chips = wafer_count * chips_per_wafer * expected_yield
    return {"total_cost": total, "expected_good_chips": good_chips, "cost_per_good_chip": total / good_chips}


def fabrication_schedule(steps: list[dict[str, Any]], *, start_date: str | None = None) -> dict[str, Any]:
    current = date.fromisoformat(start_date) if start_date else date.today()
    rows = []
    for step in steps:
        duration = int(step["duration_days"])
        start = current
        current += timedelta(days=duration)
        rows.append({**step, "start": start.isoformat(), "finish": current.isoformat()})
    return {"steps": rows, "projected_completion": current.isoformat()}


def initialize_inventory_database(path: str | Path) -> Path:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS chips(id TEXT PRIMARY KEY, wafer_id TEXT NOT NULL, die_x INTEGER, die_y INTEGER, status TEXT NOT NULL, location TEXT, metadata_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS schedule(id INTEGER PRIMARY KEY, step TEXT NOT NULL, planned_start TEXT, planned_finish TEXT, actual_finish TEXT, status TEXT NOT NULL);
        """)
    return database


def record_chip_inventory(path: str | Path, *, chip_id: str, wafer_id: str, die_x: int, die_y: int, status: str, location: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    database = initialize_inventory_database(path)
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT OR REPLACE INTO chips VALUES (?, ?, ?, ?, ?, ?, ?)", (chip_id, wafer_id, die_x, die_y, status, location, json.dumps(metadata or {})))
    return {"chip_id": chip_id, "status": status, "database_path": str(database)}


def wafer_dashboard_data(path: str | Path) -> dict[str, Any]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT wafer_id, status, COUNT(*) FROM chips GROUP BY wafer_id, status").fetchall()
    return {"schema": "text-to-gds.wafer-dashboard.v1", "counts": [{"wafer_id": row[0], "status": row[1], "count": row[2]} for row in rows]}


def detect_fabrication_anomalies(records: list[dict[str, float]], fields: list[str], *, z_threshold: float = 3.0) -> dict[str, Any]:
    matrix = np.asarray([[float(record[field]) for field in fields] for record in records])
    center, spread = np.median(matrix, axis=0), np.median(np.abs(matrix - np.median(matrix, axis=0)), axis=0) * 1.4826
    z = np.abs((matrix - center) / np.maximum(spread, 1e-30))
    flagged = np.where(np.any(z > z_threshold, axis=1))[0].tolist()
    return {"anomaly_indices": flagged, "anomaly_count": len(flagged), "robust_z_scores": z.tolist()}


def predict_process_drift(timestamps: list[float], values: list[float], *, future_time: float) -> dict[str, float]:
    time, data = np.asarray(timestamps), np.asarray(values)
    if time.shape != data.shape or time.size < 3:
        raise ValueError("At least three process observations are required")
    slope, intercept = np.polyfit(time, data, 1)
    residual = data - (slope * time + intercept)
    return {"predicted_value": float(slope * future_time + intercept), "drift_per_time": float(slope), "prediction_sigma": float(np.std(residual, ddof=1))}


def optimize_fabrication_recipe(history: list[dict[str, Any]], targets: dict[str, float], controls: list[str]) -> dict[str, Any]:
    metrics = list(targets)
    x = np.asarray([[1.0] + [float(row["controls"][name]) for name in controls] for row in history])
    y = np.asarray([[float(row["metrics"][name]) for name in metrics] for row in history])
    coefficients = np.linalg.lstsq(x, y, rcond=None)[0]
    target = np.asarray([targets[name] for name in metrics])
    control = np.linalg.pinv(coefficients[1:].T) @ (target - coefficients[0])
    return {"recommended_controls": dict(zip(controls, control.tolist(), strict=True)), "model": "multivariate_linear_inverse", "sample_count": len(history)}


def fabrication_report(wafer: dict[str, Any], measurements: list[dict[str, Any]], anomalies: dict[str, Any] | None = None) -> dict[str, Any]:
    numeric = [float(row["ic_ua"]) for row in measurements if row.get("ic_ua") is not None]
    return {"schema": "text-to-gds.fabrication-report.v1", "wafer": wafer, "measurement_count": len(measurements), "ic_ua": {"mean": float(np.mean(numeric)), "sigma": float(np.std(numeric))} if numeric else None, "anomalies": anomalies or {}, "release_ready": bool(measurements) and not (anomalies or {}).get("anomaly_count")}
