"""Local fabrication-process database and process-aware JJ design correction."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FabricationProcess:
    process_id: str
    name: str
    oxidation_pressure_mbar: float
    oxidation_time_s: float
    room_temperature_c: float
    target_jc: float
    measured_jc: float
    sigma_jc: float
    wafer_position: str
    lithography_sigma_fraction: float
    capacitance_sigma_fraction: float
    acceptance_tolerance_fraction: float
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FabricationProcess":
        required = {
            "process_id",
            "name",
            "oxidation_pressure_mbar",
            "oxidation_time_s",
            "room_temperature_c",
            "target_Jc_ua_per_um2",
            "measured_Jc_ua_per_um2",
            "sigma_Jc_ua_per_um2",
            "wafer_position",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Process record missing required fields: {missing}")
        process = cls(
            process_id=str(data["process_id"]),
            name=str(data["name"]),
            oxidation_pressure_mbar=float(data["oxidation_pressure_mbar"]),
            oxidation_time_s=float(data["oxidation_time_s"]),
            room_temperature_c=float(data["room_temperature_c"]),
            target_jc=float(data["target_Jc_ua_per_um2"]),
            measured_jc=float(data["measured_Jc_ua_per_um2"]),
            sigma_jc=float(data["sigma_Jc_ua_per_um2"]),
            wafer_position=str(data["wafer_position"]),
            lithography_sigma_fraction=float(data.get("lithography_sigma_fraction", 0.0)),
            capacitance_sigma_fraction=float(data.get("capacitance_sigma_fraction", 0.0)),
            acceptance_tolerance_fraction=float(data.get("acceptance_tolerance_fraction", 0.1)),
            raw=data,
        )
        if min(process.target_jc, process.measured_jc, process.sigma_jc) <= 0.0:
            raise ValueError("Jc target, measurement, and sigma must be positive")
        return process

    def expected_ic_yield(self) -> float:
        relative_sigma = self.sigma_jc / self.measured_jc
        z = self.acceptance_tolerance_fraction / max(relative_sigma, 1e-15)
        return math.erf(z / math.sqrt(2.0))

    def corrected_junction_area(self, nominal_area_um2: float) -> float:
        if nominal_area_um2 <= 0.0:
            raise ValueError("nominal_area_um2 must be positive")
        return nominal_area_um2 * self.target_jc / self.measured_jc


class ProcessDatabase:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def list(self) -> list[FabricationProcess]:
        records = []
        for path in sorted(self.root.glob("*.json")):
            records.append(FabricationProcess.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return records

    def get(self, query: str) -> FabricationProcess:
        normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
        candidates = self.list()
        for process in candidates:
            names = {process.process_id.lower(), process.name.lower()}
            if query.lower() in names:
                return process
        scored = []
        query_tokens = set(normalized.split())
        for process in candidates:
            tokens = set(re.sub(r"[^a-z0-9]+", " ", process.name.lower()).split())
            scored.append((len(query_tokens & tokens), process))
        if scored and max(score for score, _ in scored) > 0:
            return max(scored, key=lambda item: item[0])[1]
        raise KeyError(f"Unknown process {query!r}; available: {[p.name for p in candidates]}")


def plan_process_aware_jpa(
    prompt: str,
    *,
    database_root: str | Path,
    nominal_junction_area_um2: float = 0.0484,
) -> dict[str, Any]:
    """Resolve a process named in a prompt and return corrected JJ/yield inputs."""
    frequency_match = re.search(r"(\d+(?:\.\d+)?)\s*ghz", prompt, re.IGNORECASE)
    if not frequency_match:
        raise ValueError("Prompt must include a target frequency in GHz")
    database = ProcessDatabase(database_root)
    processes = database.list()
    process = next(
        (candidate for candidate in processes if candidate.name.lower() in prompt.lower()),
        None,
    )
    if process is None:
        prompt_tokens = set(re.sub(r"[^a-z0-9]+", " ", prompt.lower()).split())
        scored = [
            (
                len(
                    prompt_tokens
                    & set(re.sub(r"[^a-z0-9]+", " ", candidate.name.lower()).split())
                ),
                candidate,
            )
            for candidate in processes
        ]
        process = max(scored, key=lambda item: item[0])[1] if scored else None
    if process is None:
        raise KeyError("No fabrication process matched the prompt")
    corrected_area = process.corrected_junction_area(nominal_junction_area_um2)
    expected_ic = corrected_area * process.measured_jc
    return {
        "schema": "text-to-gds.process-aware-design.v1",
        "prompt": prompt,
        "target_frequency_ghz": float(frequency_match.group(1)),
        "process": process.raw,
        "design_correction": {
            "nominal_junction_area_um2": nominal_junction_area_um2,
            "corrected_junction_area_um2": corrected_area,
            "area_scale": corrected_area / nominal_junction_area_um2,
            "expected_critical_current_ua": expected_ic,
        },
        "expected_ic_yield": process.expected_ic_yield(),
        "expected_ic_yield_percent": 100.0 * process.expected_ic_yield(),
        "validity": process.raw.get("provenance", {}).get("calibration_status"),
    }
