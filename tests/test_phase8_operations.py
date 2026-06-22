from __future__ import annotations

from text_to_gds.phase8_operations import (
    artifact_hash,
    classify_vna_trace,
    dataset_version,
    foundry_handoff,
    manufacturing_readiness,
    masked_layout_pretraining,
    paper_reproduction_report,
    paper_to_benchmark,
    recommend_next_device,
    research_critique,
)


def test_literature_dataset_and_layout_operations():
    source = {"identifier": "10.1/test"}
    benchmark = paper_to_benchmark(source, {"frequency": 6.0}, {"gain": 20.0})
    report = paper_reproduction_report(benchmark, {"gain": 19.0})
    assert report["score"] == 0.95
    version = dataset_version([{"process_hash": "p", "measurement_hash": "m"}])
    assert len(version["version_hash"]) == 64
    assert artifact_hash({"a": 1}) == artifact_hash({"a": 1})
    masked = masked_layout_pretraining([1, 2, 3, 4], mask_fraction=0.25)
    assert len(masked["mask_indices"]) == 1


def test_measurement_signoff_and_research_operations():
    trace = classify_vna_trace([1, 2, 3], [0, -10, 0])
    assert trace["label"] == "resonance_dip"
    handoff = foundry_handoff({"gds_path": "a.gds", "gds_hash": "x", "process": "p@1.0.0", "drc_report": "d", "lvs_report": "l", "layer_map": {}, "wafer_map": "w"})
    assert handoff["ready"] is False  # empty layer map is rejected
    readiness = manufacturing_readiness({name: True for name in ["design_verified", "process_compatible", "yield_estimated", "reliability_qualified", "supply_chain_ready", "production_tracking_ready"]})
    assert readiness["passed"]
    assert not research_critique({})["publishable"]
    selected = recommend_next_device([{"topology": "jpa"}], [{"topology": "jpa", "expected_improvement": 0.1}, {"topology": "snail", "expected_improvement": 0.05}])
    assert selected["selected"]["topology"] == "snail"
