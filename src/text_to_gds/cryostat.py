"""Cryogenic input/output-chain noise and dynamic-range calculations."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _db_to_power(value_db: float) -> float:
    return 10.0 ** (value_db / 10.0)


def analyze_cryogenic_chain(path: str | Path, *, source_temperature_k: float = 300.0) -> dict[str, Any]:
    """Calculate cascaded Friis noise and available power at each stage."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    stages = data.get("stages", [])
    if not stages:
        raise ValueError("Cryogenic chain must contain stages")
    cumulative_gain = 1.0
    equivalent_input_noise = 0.0
    power_dbm = float(data.get("input_power_dbm", 0.0))
    propagated_noise_temperature = source_temperature_k
    rows = []
    for stage in stages:
        kind = stage["kind"]
        temperature = float(stage["temperature_k"])
        if kind == "attenuator":
            loss_db = float(stage["loss_db"])
            loss = _db_to_power(loss_db)
            stage_gain = 1.0 / loss
            stage_noise = (loss - 1.0) * temperature
            propagated_noise_temperature = (
                propagated_noise_temperature / loss + temperature * (1.0 - 1.0 / loss)
            )
            power_dbm -= loss_db
        elif kind == "amplifier":
            gain_db = float(stage["gain_db"])
            stage_gain = _db_to_power(gain_db)
            stage_noise = float(stage["noise_temperature_k"])
            propagated_noise_temperature += stage_noise
            power_dbm += gain_db
        else:
            raise ValueError(f"Unknown cryogenic stage kind: {kind}")
        equivalent_input_noise += stage_noise / cumulative_gain
        cumulative_gain *= stage_gain
        rows.append(
            {
                **stage,
                "power_after_stage_dbm": power_dbm,
                "cumulative_gain_db": 10.0 * math.log10(cumulative_gain),
                "input_referred_noise_temperature_k": equivalent_input_noise,
                "propagated_noise_temperature_k": propagated_noise_temperature,
            }
        )
    jpa = next((row for row in rows if row["name"].lower() == "jpa"), None)
    jpa_input_power = None
    jpa_headroom_db = None
    jpa_input_noise_temperature = None
    system_noise_at_jpa_input = None
    if jpa is not None:
        index = rows.index(jpa)
        jpa_input_power = (
            float(data.get("input_power_dbm", 0.0))
            if index == 0
            else float(rows[index - 1]["power_after_stage_dbm"])
        )
        jpa_input_noise_temperature = (
            source_temperature_k
            if index == 0
            else float(rows[index - 1]["propagated_noise_temperature_k"])
        )
        downstream_added_noise = 0.0
        gain_before = 1.0
        for downstream in stages[index:]:
            if downstream["kind"] == "amplifier":
                downstream_added_noise += float(downstream["noise_temperature_k"]) / gain_before
                gain_before *= _db_to_power(float(downstream["gain_db"]))
            else:
                loss = _db_to_power(float(downstream["loss_db"]))
                downstream_added_noise += (loss - 1.0) * float(downstream["temperature_k"]) / gain_before
                gain_before /= loss
        system_noise_at_jpa_input = jpa_input_noise_temperature + downstream_added_noise
        if "input_p1db_dbm" in jpa:
            jpa_headroom_db = float(jpa["input_p1db_dbm"]) - jpa_input_power
    return {
        "schema": "text-to-gds.cryogenic-chain-analysis.v1",
        "name": data.get("name"),
        "source_temperature_k": source_temperature_k,
        "system_noise_temperature_k": source_temperature_k + equivalent_input_noise,
        "added_input_noise_temperature_k": equivalent_input_noise,
        "total_gain_db": 10.0 * math.log10(cumulative_gain),
        "available_jpa_input_power_dbm": jpa_input_power,
        "jpa_headroom_to_p1db_db": jpa_headroom_db,
        "noise_temperature_at_jpa_input_k": jpa_input_noise_temperature,
        "system_noise_referred_to_jpa_input_k": system_noise_at_jpa_input,
        "stages": rows,
        "validity": "Friis small-signal noise model; excludes mismatch, standing waves, and nonlinear heating.",
    }
