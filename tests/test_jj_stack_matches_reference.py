from __future__ import annotations

import json
from pathlib import Path

from text_to_gds.reference_compare import golden_compare


ROOT = Path(__file__).resolve().parents[1]


def test_jj_stack_reference_requires_nb_trilayer_features() -> None:
    device = {
        "process": "nb_trilayer",
        "layers": {
            "M1": "bottom electrode",
            "JJ": "AlOx tunnel barrier overlap",
            "M2": "top electrode",
            "VIA12": "via enclosure",
        },
        "rules": {"junction isolation": True},
    }
    report = golden_compare(device, "process")
    assert report["device_family"] == "process"
    assert report["topology_score"] == 1.0
    assert report["fabrication_warnings"] == []


def test_no_numeric_reference_value_lacks_citation() -> None:
    reference_paths = list((ROOT / "references").rglob("*.json")) + [ROOT / "process_reference.json"]

    def walk(obj: object, path: Path) -> None:
        if isinstance(obj, dict):
            has_number = any(key in obj and isinstance(obj[key], (int, float)) for key in ("value", "min", "max"))
            if has_number:
                assert obj.get("citation"), f"missing citation in {path}: {obj}"
            for value in obj.values():
                walk(value, path)
        elif isinstance(obj, list):
            for value in obj:
                walk(value, path)

    for path in reference_paths:
        walk(json.loads(path.read_text(encoding="utf-8")), path)
