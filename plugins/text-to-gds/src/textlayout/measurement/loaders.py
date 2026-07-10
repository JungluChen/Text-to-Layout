"""Load measurement/prediction records from JSON or CSV.

CSV columns map 1:1 to :class:`MeasurementRecord` field names; empty cells
become ``None`` for optional numeric fields. The ``synthetic`` column parses
"true"/"false" (case-insensitive) and DEFAULTS TO TRUE when absent — a
missing flag can never promote fixture data to real-measurement status.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from textlayout.measurement.models import MeasurementRecord, SimulatedPrediction

_NUMERIC_FIELDS = (
    "measured_frequency_ghz",
    "measured_capacitance_pf",
    "measured_inductance_nh",
    "measured_q",
    "measured_t1_us",
    "measured_t2_us",
    "temperature_k",
)


def load_measurements(path: str | Path) -> list[MeasurementRecord]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return _load_measurements_csv(source)
    data = json.loads(source.read_text(encoding="utf-8"))
    return [MeasurementRecord.model_validate(item) for item in data]


def load_predictions(path: str | Path) -> list[SimulatedPrediction]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [SimulatedPrediction.model_validate(item) for item in data]


def _load_measurements_csv(source: Path) -> list[MeasurementRecord]:
    records: list[MeasurementRecord] = []
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item: dict[str, object] = {}
            for key, raw in row.items():
                if key is None:
                    continue
                value = (raw or "").strip()
                if value == "":
                    continue
                if key in _NUMERIC_FIELDS:
                    item[key] = float(value)
                elif key == "synthetic":
                    item[key] = value.casefold() in {"true", "1", "yes"}
                elif key == "notes":
                    item[key] = [part.strip() for part in value.split(";") if part.strip()]
                else:
                    item[key] = value
            records.append(MeasurementRecord.model_validate(item))
    return records
