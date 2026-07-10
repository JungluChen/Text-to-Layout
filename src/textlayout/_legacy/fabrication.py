"""Fabrication run tracking, JJ history, process prediction, and SEM metrology."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np


def initialize_fabrication_database(path: str | Path) -> Path:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS wafer_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wafer_id TEXT NOT NULL UNIQUE,
                process_id TEXT NOT NULL,
                process_version TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS oxidation_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id TEXT NOT NULL UNIQUE,
                pressure_mbar REAL NOT NULL,
                time_s REAL NOT NULL,
                temperature_c REAL NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS junction_measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wafer_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                x_mm REAL NOT NULL,
                y_mm REAL NOT NULL,
                area_um2 REAL NOT NULL,
                ic_ua REAL NOT NULL,
                rn_ohm REAL,
                measured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT NOT NULL,
                FOREIGN KEY(wafer_id) REFERENCES wafer_runs(wafer_id)
            );
            """
        )
    return database


def record_wafer_run(
    path: str | Path,
    *,
    wafer_id: str,
    process_id: str,
    process_version: str,
    status: str = "planned",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    database = initialize_fabrication_database(path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO wafer_runs(wafer_id, process_id, process_version, status, metadata_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(wafer_id) DO UPDATE SET status=excluded.status,
                   process_id=excluded.process_id, process_version=excluded.process_version,
                   metadata_json=excluded.metadata_json""",
            (wafer_id, process_id, process_version, status, json.dumps(metadata or {})),
        )
    return {"wafer_id": wafer_id, "database_path": str(database), "status": status}


def record_oxidation_recipe(
    path: str | Path,
    *,
    recipe_id: str,
    pressure_mbar: float,
    time_s: float,
    temperature_c: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if pressure_mbar <= 0.0 or time_s <= 0.0:
        raise ValueError("Oxidation pressure and time must be positive")
    database = initialize_fabrication_database(path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO oxidation_recipes(recipe_id, pressure_mbar, time_s, temperature_c, metadata_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(recipe_id) DO UPDATE SET pressure_mbar=excluded.pressure_mbar,
                   time_s=excluded.time_s, temperature_c=excluded.temperature_c,
                   metadata_json=excluded.metadata_json""",
            (recipe_id, pressure_mbar, time_s, temperature_c, json.dumps(metadata or {})),
        )
    return {"recipe_id": recipe_id, "dose_mbar_s": pressure_mbar * time_s, "database_path": str(database)}


def record_junction_measurement(
    path: str | Path,
    *,
    wafer_id: str,
    device_id: str,
    x_mm: float,
    y_mm: float,
    area_um2: float,
    ic_ua: float,
    rn_ohm: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if area_um2 <= 0.0 or ic_ua <= 0.0:
        raise ValueError("Junction area and Ic must be positive")
    database = initialize_fabrication_database(path)
    with sqlite3.connect(database) as connection:
        cursor = connection.execute(
            """INSERT INTO junction_measurements
               (wafer_id, device_id, x_mm, y_mm, area_um2, ic_ua, rn_ohm, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (wafer_id, device_id, x_mm, y_mm, area_um2, ic_ua, rn_ohm, json.dumps(metadata or {})),
        )
        measurement_id = int(cursor.lastrowid)
    return {
        "measurement_id": measurement_id,
        "critical_current_density_ua_per_um2": ic_ua / area_um2,
        "icrn_uv": ic_ua * rn_ohm if rn_ohm is not None else None,
        "database_path": str(database),
    }


def predict_wafer_ic(
    path: str | Path,
    *,
    wafer_id: str,
    x_mm: float,
    y_mm: float,
    area_um2: float,
) -> dict[str, Any]:
    """Fit Jc = b0 + bx*x + by*y + br*r^2 from measured wafer history."""
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT x_mm, y_mm, area_um2, ic_ua FROM junction_measurements WHERE wafer_id=?",
            (wafer_id,),
        ).fetchall()
    if not rows:
        raise ValueError(f"No junction measurements for wafer {wafer_id!r}")
    design = np.asarray([[1.0, row[0], row[1], row[0] ** 2 + row[1] ** 2] for row in rows])
    jc = np.asarray([row[3] / row[2] for row in rows])
    coefficients = np.linalg.lstsq(design, jc, rcond=None)[0]
    feature = np.asarray([1.0, x_mm, y_mm, x_mm**2 + y_mm**2])
    predicted_jc = max(float(feature @ coefficients), 0.0)
    residual = jc - design @ coefficients
    sigma = float(np.std(residual, ddof=min(1, len(residual) - 1)))
    return {
        "schema": "text-to-gds.wafer-ic-prediction.v1",
        "wafer_id": wafer_id,
        "position_mm": [x_mm, y_mm],
        "sample_count": len(rows),
        "predicted_jc_ua_per_um2": predicted_jc,
        "predicted_ic_ua": predicted_jc * area_um2,
        "prediction_sigma_ic_ua": sigma * area_um2,
        "model": "quadratic_radial_least_squares",
    }


def fabrication_yield_prediction(
    *,
    nominal_frequency_ghz: float,
    nominal_gain_db: float,
    samples: int = 10000,
    lithography_sigma_fraction: float = 0.02,
    oxide_sigma_fraction: float = 0.05,
    thickness_sigma_fraction: float = 0.02,
    frequency_tolerance_fraction: float = 0.05,
    gain_tolerance_db: float = 2.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Monte-Carlo process variation and joint frequency/gain yield."""
    if samples < 10:
        raise ValueError("samples must be >= 10")
    rng = np.random.default_rng(seed)
    lithography = rng.normal(0.0, lithography_sigma_fraction, samples)
    oxide = rng.normal(0.0, oxide_sigma_fraction, samples)
    thickness = rng.normal(0.0, thickness_sigma_fraction, samples)
    frequency = nominal_frequency_ghz * np.sqrt(np.maximum((1.0 + lithography) * (1.0 + oxide), 1e-6))
    gain = nominal_gain_db - 20.0 * np.abs(oxide) - 8.0 * np.abs(thickness)
    frequency_ok = np.abs(frequency / nominal_frequency_ghz - 1.0) <= frequency_tolerance_fraction
    gain_ok = np.abs(gain - nominal_gain_db) <= gain_tolerance_db
    return {
        "schema": "text-to-gds.fabrication-yield.v1",
        "samples": samples,
        "yield_fraction": float(np.mean(frequency_ok & gain_ok)),
        "frequency_ghz": {"mean": float(np.mean(frequency)), "sigma": float(np.std(frequency))},
        "gain_db": {"mean": float(np.mean(gain)), "sigma": float(np.std(gain))},
        "corner_analysis": {
            "low_frequency_ghz": float(np.quantile(frequency, 0.01)),
            "high_frequency_ghz": float(np.quantile(frequency, 0.99)),
            "low_gain_db": float(np.quantile(gain, 0.01)),
        },
    }


def _sem_mask(path: str | Path, threshold: int | None = None) -> tuple[np.ndarray, int]:
    from PIL import Image

    gray = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
    used_threshold = int(np.median(gray)) if threshold is None else int(threshold)
    return gray >= used_threshold, used_threshold


def measure_sem_critical_dimensions(
    image_path: str | Path, *, pixel_size_nm: float, threshold: int | None = None
) -> dict[str, Any]:
    """Measure foreground run lengths in a calibrated, thresholded SEM image."""
    if pixel_size_nm <= 0.0:
        raise ValueError("pixel_size_nm must be positive")
    mask, used_threshold = _sem_mask(image_path, threshold)
    runs = []
    for row in mask:
        changes = np.diff(np.pad(row.astype(np.int8), (1, 1)))
        starts, ends = np.where(changes == 1)[0], np.where(changes == -1)[0]
        runs.extend((ends - starts).tolist())
    positive = np.asarray([run for run in runs if run > 0], dtype=float)
    if positive.size == 0:
        raise ValueError("No foreground features found in SEM image")
    dimensions = positive * pixel_size_nm
    return {
        "schema": "text-to-gds.sem-critical-dimensions.v1",
        "threshold": used_threshold,
        "pixel_size_nm": pixel_size_nm,
        "measurement_count": int(dimensions.size),
        "critical_dimension_nm": {
            "median": float(np.median(dimensions)),
            "mean": float(np.mean(dimensions)),
            "p05": float(np.quantile(dimensions, 0.05)),
            "p95": float(np.quantile(dimensions, 0.95)),
        },
        "method": "thresholded_horizontal_run_length",
    }


def compare_sem_images(
    reference_image: str | Path,
    sem_image: str | Path,
    *,
    pixel_size_nm: float,
    threshold: int | None = None,
) -> dict[str, Any]:
    """Register same-size masks by translation and report fabrication XOR error."""
    reference, ref_threshold = _sem_mask(reference_image, threshold)
    observed, sem_threshold = _sem_mask(sem_image, threshold)
    if reference.shape != observed.shape:
        raise ValueError("Reference and SEM images must have the same registered dimensions")
    best = None
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            shifted = np.roll(observed, (dy, dx), axis=(0, 1))
            error = float(np.mean(reference != shifted))
            if best is None or error < best[0]:
                best = (error, dx, dy, shifted)
    assert best is not None
    xor_pixels = int(np.sum(reference != best[3]))
    return {
        "schema": "text-to-gds.sem-layout-comparison.v1",
        "registration_pixels": [best[1], best[2]],
        "xor_fraction": best[0],
        "xor_area_um2": xor_pixels * (pixel_size_nm / 1000.0) ** 2,
        "reference_threshold": ref_threshold,
        "sem_threshold": sem_threshold,
        "model_validity": "Requires a pre-rendered GDS reference at the same scale and orientation as the SEM image.",
    }
