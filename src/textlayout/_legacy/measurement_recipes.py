"""Executable QCoDeS-oriented JPA measurement recipe templates."""

from __future__ import annotations

import csv
import json
import math
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import numpy as np

RECIPES = {
    "gain_map": {"x": "frequency_ghz", "y": "flux_phi0", "metric": "gain_db"},
    "flux_map": {"x": "frequency_ghz", "y": "flux_phi0", "metric": "gain_db"},
    "pump_map": {"x": "frequency_ghz", "y": "pump_power_dbm", "metric": "gain_db"},
    "noise_temperature": {"x": "frequency_ghz", "y": "pump_power_dbm", "metric": "noise_temperature_k"},
    "compression": {"x": "input_power_dbm", "y": "pump_power_dbm", "metric": "gain_db"},
    "squeezing": {"x": "relative_phase_deg", "y": "pump_power_dbm", "metric": "quadrature_db"},
}


def _recipe_grid(recipe: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if recipe not in RECIPES:
        raise ValueError(f"Unknown recipe {recipe!r}; choose {sorted(RECIPES)}")
    if recipe in {"gain_map", "flux_map"}:
        x = np.linspace(4.0, 8.0, 161)
        y = np.linspace(-0.5, 0.5, 101)
        xx, yy = np.meshgrid(x, y)
        resonance = 6.0 * np.sqrt(np.maximum(np.abs(np.cos(math.pi * yy)), 0.04))
        metric = 20.0 / (1.0 + ((xx - resonance) / 0.18) ** 2)
    elif recipe == "pump_map":
        x = np.linspace(4.0, 8.0, 161)
        y = np.linspace(-95.0, -65.0, 101)
        xx, yy = np.meshgrid(x, y)
        pump_factor = np.clip((yy + 90.0) / 18.0, 0.0, 1.0)
        metric = 24.0 * pump_factor / (1.0 + ((xx - 6.0) / 0.7) ** 4)
    elif recipe == "noise_temperature":
        x = np.linspace(4.0, 8.0, 161)
        y = np.linspace(-95.0, -65.0, 101)
        xx, yy = np.meshgrid(x, y)
        metric = 0.145 + 0.02 * ((xx - 6.0) / 2.0) ** 2 + 0.08 * ((yy + 78.0) / 17.0) ** 2
    elif recipe == "compression":
        x = np.linspace(-140.0, -80.0, 161)
        y = np.linspace(-88.0, -70.0, 91)
        xx, yy = np.meshgrid(x, y)
        small_signal = np.clip(20.0 + 0.5 * (yy + 78.0), 0.0, 26.0)
        metric = small_signal - 10.0 * np.log10(1.0 + 10.0 ** ((xx + 105.0) / 10.0))
    else:
        x = np.linspace(0.0, 360.0, 181)
        y = np.linspace(-88.0, -70.0, 91)
        xx, yy = np.meshgrid(x, y)
        amplitude = np.clip((yy + 88.0) / 18.0, 0.0, 1.0)
        metric = -10.0 * amplitude * np.cos(np.deg2rad(xx))
    return x, y, metric


def run_measurement_recipe(
    recipe: str,
    *,
    json_path: str | Path,
    csv_path: str | Path,
    plot_path: str | Path,
    source: str = "simulation_template",
) -> dict[str, Any]:
    """Run the deterministic dry-run recipe and emit the same shape as hardware data."""
    definition = RECIPES[recipe]
    x, y, values = _recipe_grid(recipe)
    json_file, csv_file, plot_file = Path(json_path), Path(csv_path), Path(plot_path)
    for path in (json_file, csv_file, plot_file):
        path.parent.mkdir(parents=True, exist_ok=True)
    with csv_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([definition["x"], definition["y"], definition["metric"]])
        for row_index, y_value in enumerate(y):
            for column_index, x_value in enumerate(x):
                writer.writerow([x_value, y_value, values[row_index, column_index]])

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    image = ax.pcolormesh(x, y, values, shading="auto", cmap="viridis")
    fig.colorbar(image, ax=ax, label=definition["metric"].replace("_", " "))
    ax.set(xlabel=definition["x"].replace("_", " "), ylabel=definition["y"].replace("_", " "), title=recipe.replace("_", " ").title())
    fig.savefig(plot_file, dpi=200)
    plt.close(fig)
    result = {
        "schema": "text-to-gds.measurement-recipe-result.v1",
        "recipe": recipe,
        "source": source,
        "qcodes_available": find_spec("qcodes") is not None,
        "axes": definition,
        "shape": list(values.shape),
        "metric_summary": {"minimum": float(np.min(values)), "maximum": float(np.max(values)), "mean": float(np.mean(values))},
        "artifacts": {"json_path": str(json_file), "csv_path": str(csv_file), "plot_path": str(plot_file)},
        "validity": "Dry-run data validates recipe, plotting, and artifact shape; bind QCoDeS Parameters before instrument use.",
    }
    json_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def write_measurement_recipe(
    recipe: str,
    *,
    script_path: str | Path,
    plan_path: str | Path,
) -> dict[str, Any]:
    if recipe not in RECIPES:
        raise ValueError(f"Unknown recipe {recipe!r}; choose {sorted(RECIPES)}")
    script, plan = Path(script_path), Path(plan_path)
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        f'''# Generated JPA measurement recipe. Bind real QCoDeS Parameters before hardware use.
from pathlib import Path
from textlayout._legacy.measurement_recipes import run_measurement_recipe

OUT = Path(__file__).resolve().parent
result = run_measurement_recipe(
    {recipe!r},
    json_path=OUT / "{recipe}.result.json",
    csv_path=OUT / "{recipe}.csv",
    plot_path=OUT / "{recipe}.png",
)
print(result)
''',
        encoding="utf-8",
    )
    result = {
        "schema": "text-to-gds.measurement-recipe.v1",
        "recipe": recipe,
        "axes": RECIPES[recipe],
        "script_path": str(script),
        "plan_path": str(plan),
        "instrument_roles": ["vna", "pump_source", "flux_source", "spectrum_analyzer"],
        "safety": ["start sources RF-off", "apply configured power limits", "ramp flux and pump", "never auto-connect hardware in dry-run"],
    }
    plan.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
