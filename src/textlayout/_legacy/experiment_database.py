"""SQLite experiment records and measurement-driven model correction."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def initialize_experiment_database(path: str | Path) -> Path:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                process_id TEXT,
                device_id TEXT NOT NULL,
                design_json TEXT NOT NULL,
                measurement_json TEXT NOT NULL
            )
            """
        )
    return database


def record_experiment(
    path: str | Path,
    *,
    device_id: str,
    process_id: str | None,
    design: dict[str, Any],
    measurement: dict[str, Any],
) -> dict[str, Any]:
    database = initialize_experiment_database(path)
    with sqlite3.connect(database) as connection:
        cursor = connection.execute(
            "INSERT INTO experiment_runs(process_id, device_id, design_json, measurement_json) VALUES (?, ?, ?, ?)",
            (process_id, device_id, json.dumps(design), json.dumps(measurement)),
        )
        run_id = int(cursor.lastrowid)
    target_frequency = float(design.get("target_frequency_ghz", 0.0) or 0.0)
    measured_frequency = float(measurement.get("center_frequency_ghz", 0.0) or 0.0)
    frequency_scale = target_frequency / measured_frequency if measured_frequency > 0.0 else None
    measured_ic = measurement.get("critical_current_ua")
    target_ic = design.get("target_critical_current_ua")
    area_scale = (
        float(target_ic) / float(measured_ic)
        if measured_ic not in (None, 0) and target_ic is not None
        else None
    )
    return {
        "schema": "text-to-gds.experiment-feedback.v1",
        "run_id": run_id,
        "database_path": str(database),
        "model_correction": {
            "frequency_scale": frequency_scale,
            "junction_area_scale": area_scale,
        },
        "next_design": {
            "apply_frequency_scale": frequency_scale is not None,
            "apply_junction_area_scale": area_scale is not None,
        },
    }
