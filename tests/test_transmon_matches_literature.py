from __future__ import annotations

from pathlib import Path

from text_to_gds.device_library import Transmon
from text_to_gds.reference_compare import golden_compare


ROOT = Path(__file__).resolve().parents[1]


def test_transmon_reports_golden_reference_metrics() -> None:
    report = golden_compare(Transmon(frequency_ghz=5.0, anharmonicity_mhz=-250.0), "transmon")
    assert report["schema"] == "text-to-gds.golden-comparison.v1"
    assert report["device_family"] == "transmon"
    assert report["topology_score"] >= 0.75
    assert "pad_width_um" in report["parameter_error"]
    assert "ej_over_ec" in report["parameter_error"]
    assert report["parameter_error"]["ej_over_ec"]["status"] in {"in_range", "compared"}
    assert report["comparisons"]


def test_transmon_references_have_citations() -> None:
    for path in (ROOT / "references" / "transmon").glob("*.json"):
        data = path.read_text(encoding="utf-8")
        assert "citation" in data
