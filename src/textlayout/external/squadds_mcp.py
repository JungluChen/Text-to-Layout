"""SQuADDS MCP integration boundary.

SQuADDS may provide validated-design search results and priors. Those priors
must be regenerated through Text-to-Layout and pass normal geometry/solver gates
before any PHYSICS_VERIFIED claim is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SquaddsPrior:
    design_id: str
    hamiltonian_parameters: dict[str, float]
    geometry_priors: dict[str, float]
    dataset_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "textlayout.squadds-prior.v1",
            "source": "SQuADDS",
            "evidence_status": "PRIOR_ONLY",
            "physics_verified": False,
            "design_id": self.design_id,
            "hamiltonian_parameters": dict(self.hamiltonian_parameters),
            "geometry_priors": dict(self.geometry_priors),
            "dataset_metadata": dict(self.dataset_metadata),
        }


# Deliberately limited to unambiguous frequency fields in the pinned WM1 data.
# The upstream spelling is retained in provenance, not silently corrected there.
_WM1_FIELDS = {
    "resonator_frequency_hz": ("F_res_GHz", "GHz", 1e9),
    "qubit_frequency_hz": ("F_01_GHz", "GHz", 1e9),
    "anharmonicity_hz": ("Anharmocity_MHz", "MHz", 1e6),
}


def load_wm1_prior(database: str | Path, device_id: str) -> SquaddsPrior:
    """Read one exact WM1 device from pinned local bytes; never fetch or simulate.

    Frequency values are ordinary Hz, not angular frequency. The result contains
    published priors only, with no geometry inferred from measured frequencies.
    """
    import hashlib
    import json
    import math

    from textlayout.verification.squadds_reference import ASSETS

    if device_id not in {f"qubit_{i}" for i in range(1, 7)}:
        raise ValueError("device_id must be qubit_1 through qubit_6")
    path = Path(database)
    with path.open("rb") as source:
        payload = source.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        raise ValueError("WM1 database exceeds the 1 MiB limit")
    asset = ASSETS["measured_device_database.json"]
    digest = hashlib.sha256(payload).hexdigest()
    if digest != asset["sha256"]:
        raise ValueError("SHA-256 mismatch for pinned WM1 database")
    rows = json.loads(payload.decode("utf-8"))
    if not isinstance(rows, list):
        raise ValueError("WM1 database must contain a list of records")
    matches = [row for row in rows if isinstance(row, dict)
               and isinstance(row.get("contrib_info"), dict)
               and row["contrib_info"].get("name") == "WM1"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one WM1 record")
    try:
        results = matches[0]["measured_results"]
        if len(results) != 1 or len(results[0]["H_params"]) != 1:
            raise ValueError("Expected one WM1 measurement/H_params group")
        devices = results[0]["H_params"][0]
        if set(devices) != {f"qubit_{i}" for i in range(1, 7)}:
            raise ValueError("Expected the six WM1 device records")
        values = devices[device_id]
        converted: dict[str, float] = {}
        fields: dict[str, Any] = {}
        for name, (field_name, unit, scale) in _WM1_FIELDS.items():
            raw = values[field_name]
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"Non-numeric WM1 field: {field_name}")
            value = float(raw) * scale
            if not math.isfinite(value):
                raise ValueError(f"Non-finite WM1 field: {field_name}")
            if name != "anharmonicity_hz" and value <= 0:
                raise ValueError(f"Non-positive WM1 frequency: {field_name}")
            converted[name] = value
            fields[name] = {"source_field": field_name, "source_value": raw,
                            "source_unit": unit, "scale_to_hz": scale, "unit": "Hz"}
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Malformed WM1 measurement structure") from exc
    return SquaddsPrior(
        design_id=f"WM1/{device_id}",
        hamiltonian_parameters=converted,
        geometry_priors={},
        dataset_metadata={
            "source_url": asset["url"], "source_revision": asset["revision"],
            "source_sha256": digest, "license": asset["license"],
            "selection": {"contribution": "WM1", "device_id": device_id,
                          "measured_results_index": 0, "H_params_index": 0},
            "fields": fields,
            "measurement_source": "Published SQuADDS WM1 records; not measured by Text-to-Layout",
            "device_to_top_variant_mapping": None,
            "electrical_reproduction_status": "NOT_EVALUATED",
            "upstream_package_executed": False,
        },
    )
