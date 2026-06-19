"""Tests for the fourth-wave modules: database, constraints, tokenizer, transformer, prediction, quality scoring."""

from __future__ import annotations

import json

from text_to_gds.gds_tokenizer import GDSTokenizer, TokenSequence
from text_to_gds.layout_transformer import (
    TransformerConfig,
    create_layout_transformer,
    decode_performance,
    predict_from_tokens,
)
from text_to_gds.physics_constraints import (
    check_bode_fano,
    check_bifurcation,
    check_flux_quantisation,
    check_kerr_limit,
    check_kinetic_inductance_fraction,
    check_manley_rowe,
    check_quantum_noise,
    check_all_constraints,
)
from text_to_gds.quality_scorer import LayoutQualityScorer
from text_to_gds.quantum_device_database import (
    DeviceRecord,
    FabricationRecord,
    GeometryRecord,
    MeasurementRecord,
    ProvenanceRecord,
    QuantumDeviceDatabase,
    SimulationRecord,
)


# ---------------------------------------------------------------------------
# Quantum Device Database
# ---------------------------------------------------------------------------


def test_device_database_record_and_query(tmp_path):
    db = QuantumDeviceDatabase(tmp_path / "test_devices.db")

    record = DeviceRecord(
        device_id="LJPA_NCU_001",
        status="simulated",
        geometry=GeometryRecord(device_type="LJPA", cpw_width_um=10.0),
        simulations=[
            SimulationRecord(engine="hfss", frequency_ghz=5.0, quality_factor=1000),
        ],
        measurements=[
            MeasurementRecord(gain_db=15.0, bandwidth_mhz=400.0),
        ],
        fabrication=FabricationRecord(process_id="ncu_alox_2026", jc_ua_per_um2=2.0),
        provenance=ProvenanceRecord(paper_doi="10.1234/example"),
        tags=["ljpa", "ncu"],
    )

    device_id = db.record_device(record)
    assert device_id == "LJPA_NCU_001"

    fetched = db.get_device("LJPA_NCU_001")
    assert fetched is not None
    assert fetched.geometry.device_type == "LJPA"
    assert fetched.geometry.cpw_width_um == 10.0
    assert len(fetched.simulations) == 1
    assert fetched.simulations[0].frequency_ghz == 5.0
    assert len(fetched.measurements) == 1
    assert fetched.measurements[0].gain_db == 15.0
    assert fetched.fabrication.process_id == "ncu_alox_2026"
    assert fetched.provenance.paper_doi == "10.1234/example"

    results = db.query_devices(device_type="LJPA", status="simulated")
    assert len(results) == 1
    assert results[0].device_id == "LJPA_NCU_001"

    summary = db.summary()
    assert summary["total_devices"] == 1
    assert summary["total_simulations"] == 1
    assert summary["total_measurements"] == 1

    db.close()


def test_device_database_gds_hash(tmp_path):
    db = QuantumDeviceDatabase(tmp_path / "test_hash.db")
    gds_file = tmp_path / "test.gds"
    gds_file.write_bytes(b"FAKE_GDS_CONTENT")
    h = db.compute_gds_hash(gds_file)
    assert len(h) == 64  # SHA-256 hex
    db.close()


def test_device_database_export_training_pairs(tmp_path):
    db = QuantumDeviceDatabase(tmp_path / "test_pairs.db")

    db.record_device(DeviceRecord(
        device_id="dev_001",
        status="simulated",
        geometry=GeometryRecord(device_type="JPA"),
        simulations=[SimulationRecord(engine="hfss", frequency_ghz=6.0)],
    ))

    db.record_device(DeviceRecord(
        device_id="dev_002",
        status="measured",
        geometry=GeometryRecord(device_type="CPW"),
    ))

    pairs = db.export_training_pairs()
    assert len(pairs) == 1  # only dev_001 has simulations
    assert pairs[0]["device_id"] == "dev_001"
    assert pairs[0]["geometry"]["device_type"] == "JPA"

    db.close()


# ---------------------------------------------------------------------------
# Physics Constraints
# ---------------------------------------------------------------------------


def test_bode_fano_feasible():
    result = check_bode_fano(gain_db=10, bandwidth_mhz=200, q_loaded=5)
    assert result.name == "bode_fano_gbw"
    assert isinstance(result.passed, bool)
    assert result.unit == "MHz·(lin)"


def test_bode_fano_violation():
    result = check_bode_fano(gain_db=30, bandwidth_mhz=2000, q_loaded=50)
    assert not result.passed
    assert result.severity == "error"


def test_manley_rowe_within_limit():
    result = check_manley_rowe(input_power_dbm=-100, output_power_dbm=-85)
    assert result.passed
    assert result.value == 15.0


def test_manley_rowe_exceeds_limit():
    result = check_manley_rowe(input_power_dbm=-100, output_power_dbm=-60)
    assert not result.passed
    assert result.value == 40.0


def test_quantum_noise_at_5ghz():
    result = check_quantum_noise(frequency_ghz=5.0, gain_db=20)
    assert result.passed
    assert result.value is not None
    assert result.value < 200  # quantum limit at 5 GHz ~120 mK


def test_kerr_limit_within():
    result = check_kerr_limit(anharmonicity_ghz=0.01, pump_frequency_ghz=10.0, gain_db=20)
    assert result.passed


def test_kerr_limit_exceeded():
    result = check_kerr_limit(anharmonicity_ghz=1.0, pump_frequency_ghz=10.0, gain_db=20)
    assert not result.passed


def test_bifurcation_below_threshold():
    result = check_bifurcation(pump_power_dbm=-130, bifurcation_threshold_dbm=-120)
    assert result.passed
    assert result.limit == -120.0


def test_flux_quantisation_within_range():
    result = check_flux_quantisation(
        flux_bias_ua=100.0,
        loop_area_um2=100.0,
        critical_current_ua=50.0,
    )
    assert result.name == "flux_quantisation"
    assert isinstance(result.passed, bool)


def test_kinetic_inductance_fraction_safe():
    result = check_kinetic_inductance_fraction(
        kinetic_inductance_ph=50.0,
        geometric_inductance_ph=200.0,
    )
    assert result.passed
    assert result.value < 0.5


def test_kinetic_inductance_fraction_dominant():
    result = check_kinetic_inductance_fraction(
        kinetic_inductance_ph=950.0,
        geometric_inductance_ph=50.0,
    )
    assert not result.passed


def test_check_all_constraints_aggregate():
    specs = {
        "gain_db": 20,
        "bandwidth_mhz": 500,
        "frequency_ghz": 5.0,
        "quality_factor": 10,
        "pump_power_dbm": -120,
        "kinetic_inductance_ph": 50.0,
        "geometric_inductance_ph": 200.0,
    }
    report = check_all_constraints(specs, device_id="test_device")
    assert report.device_id == "test_device"
    assert len(report.results) >= 3
    assert isinstance(report.feasible, bool)
    assert report.summary
    d = report.to_dict()
    assert d["device_id"] == "test_device"


# ---------------------------------------------------------------------------
# GDS Tokenizer
# ---------------------------------------------------------------------------


def test_tokenizer_sidecar(tmp_path):
    sidecar = {
        "ports": [
            {"center": [10.0, 0.0], "layer": [3, 0]},
            {"center": [-10.0, 0.0], "layer": [6, 0]},
        ],
        "layers": [
            {"layer": [3, 0], "name": "M1"},
            {"layer": [4, 0], "name": "JJ"},
            {"layer": [6, 0], "name": "M3"},
        ],
        "bounding_box": [200.0, 100.0],
    }
    sidecar_path = tmp_path / "test.sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    tokenizer = GDSTokenizer()
    seq = tokenizer.tokenize_sidecar(sidecar_path)

    assert isinstance(seq, TokenSequence)
    assert len(seq) > 5
    assert seq.ids[0] == tokenizer.cls_token_id()
    assert seq.ids[-1] == tokenizer.sep_token_id()
    assert seq.metadata.get("source") == str(sidecar_path)


def test_tokenizer_vocab():
    tokenizer = GDSTokenizer()
    assert tokenizer.vocab_size >= 120
    assert tokenizer.pad_token_id() == 0
    assert tokenizer.cls_token_id() == 2
    assert tokenizer.sep_token_id() == 3
    assert tokenizer.mask_token_id() == 4
    assert tokenizer.decode_token(0) == "<PAD>"
    assert tokenizer.decode_token(2) == "<CLS>"


def test_tokenizer_quantisation():
    tokenizer = GDSTokenizer(grid_nm=10.0)
    assert tokenizer._quantise(1.234) == tokenizer._quantise(1.234)


# ---------------------------------------------------------------------------
# Layout Transformer
# ---------------------------------------------------------------------------


def test_layout_transformer_numpy():
    config = TransformerConfig(vocab_size=200, max_seq_len=512, d_model=64, n_layers=2)
    model = create_layout_transformer(config)
    token_ids = [2, 100, 101, 102, 103, 104, 3]  # CLS + tokens + SEP

    out = predict_from_tokens(token_ids, model, config)
    assert "performance" in out
    assert "similarity" in out
    assert len(out["performance"]) == 8
    assert "frequency_ghz" in out["performance"]
    assert out["backend"] in ("torch", "numpy")


def test_decode_performance():
    import numpy as np
    raw = np.array([5.0, 7.0, 50.0, 6.5, -20.0, -0.1, 15.0, 500.0])
    perf = decode_performance(raw)
    assert perf["frequency_ghz"] == 5.0
    assert perf["impedance_ohm"] == 50.0
    assert perf["bandwidth_mhz"] == 500.0


# ---------------------------------------------------------------------------
# Device Prediction
# ---------------------------------------------------------------------------


def test_device_predictor_from_sidecar(tmp_path):
    sidecar = {
        "ports": [
            {"center": [10.0, 0.0], "layer": [3, 0]},
            {"center": [-10.0, 0.0], "layer": [6, 0]},
        ],
        "layers": [
            {"layer": [3, 0], "name": "M1"},
            {"layer": [4, 0], "name": "JJ"},
        ],
    }
    sidecar_path = tmp_path / "pred.sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    from text_to_gds.device_prediction import DevicePredictor
    predictor = DevicePredictor()
    result = predictor.predict_from_sidecar(sidecar_path, device_id="test_pred")

    assert result.device_id == "test_pred"
    assert "frequency_ghz" in result.predicted
    assert result.token_count > 0
    d = result.to_dict()
    assert d["device_id"] == "test_pred"


# ---------------------------------------------------------------------------
# Quality Scorer
# ---------------------------------------------------------------------------


def test_quality_scorer_basic():
    scorer = LayoutQualityScorer()
    sidecar = {
        "ports": [{"center": [10, 0], "layer": [3, 0]}, {"center": [-10, 0], "layer": [6, 0]}],
        "layers": [{"layer": [3, 0], "name": "M1"}, {"layer": [4, 0], "name": "JJ"}, {"layer": [6, 0], "name": "M3"}],
        "parameters": {"junction_area_um2": 0.0484},
        "bounding_box": [200, 100],
    }
    drc = {"status": "passed", "violations": []}
    targets = {"frequency_ghz": 5.0}

    score = scorer.score_layout(sidecar=sidecar, drc_result=drc, target_specs=targets)
    assert score.overall_score > 0
    assert score.grade in ("A", "B", "C", "D", "F")
    d = score.to_dict()
    assert 0 <= d["fabrication_score"] <= 1
    assert 0 <= d["overall_score"] <= 1


def test_quality_scorer_drc_violations():
    scorer = LayoutQualityScorer()
    drc = {"status": "failed", "violations": [{"rule": "min_width"}]}
    score = scorer.score_layout(drc_result=drc)
    assert score.fabrication_score <= 0.9
    assert any("DRC" in issue for issue in score.issues)


def test_quality_scorer_rank():
    scorer = LayoutQualityScorer()
    layouts = [
        {"sidecar": {"ports": [{"center": [10, 0], "layer": [3, 0]}, {"center": [-10, 0], "layer": [6, 0]}], "layers": [{"layer": [3, 0]}, {"layer": [4, 0]}], "bounding_box": [200, 100]}},
        {"sidecar": {"ports": [{"center": [10, 0], "layer": [3, 0]}], "layers": [], "bounding_box": [100, 50]}},
    ]
    ranked = scorer.rank_layouts(layouts)
    assert len(ranked) == 2
    assert ranked[0]["score"].overall_score >= ranked[1]["score"].overall_score
