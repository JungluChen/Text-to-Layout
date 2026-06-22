"""Phase 3 tests: rule-based review committee and the auto-repair loop."""

from __future__ import annotations

from text_to_gds.auto_repair import run_auto_repair
from text_to_gds.review import (
    review_committee,
    review_fabrication,
    review_measurement,
    review_microwave,
    review_physics,
)


def _good_cpw_evidence():
    return {
        "device": "cpw_resonator",
        "sidecar": {
            "pcell": "cpw_quarter_wave_resonator",
            "info": {"device_type": "cpw_resonator", "has_ground_plane": True},
            "ports": [{"name": "in"}, {"name": "out"}],
        },
        "drc": {"status": "passed", "violations": []},
    }


# --- Physics reviewer ---

def test_physics_fails_cpw_without_ground():
    evidence = {
        "device": "cpw",
        "sidecar": {"pcell": "cpw_straight", "info": {"device_type": "cpw"},
                    "ports": [{"name": "in"}, {"name": "out"}]},
    }
    result = review_physics(evidence)
    assert result["passed"] is False
    assert any("Z0 is undefined" in f["finding"] for f in result["findings"])


def test_physics_passes_cpw_with_ground():
    result = review_physics(_good_cpw_evidence())
    assert result["passed"] is True
    assert result["score"] == 100


def test_physics_uses_layout_summary_for_topology():
    # JPA device whose extracted GDS has no junction -> topology error.
    evidence = {
        "device": "jpa",
        "sidecar": {"info": {"device_type": "jpa", "has_ground_plane": True},
                    "ports": [{"name": "rf_in"}, {"name": "rf_out"}]},
        "layout_summary": {
            "device_class": "jpa", "junction_count": 0, "net_count": 2,
            "element_kinds": [], "polygon_connectivity_complete": True,
        },
    }
    result = review_physics(evidence)
    assert result["passed"] is False
    assert any("no Josephson junction" in f["finding"] for f in result["findings"])
    assert result["topology"]["junction_count"] == 0


def test_physics_passes_jpa_with_detected_junction():
    evidence = {
        "device": "jpa",
        "sidecar": {"info": {"device_type": "jpa", "has_ground_plane": True},
                    "ports": [{"name": "rf_in"}, {"name": "rf_out"}]},
        "layout_summary": {
            "device_class": "jpa", "junction_count": 2, "net_count": 3,
            "element_kinds": ["josephson_junction"], "polygon_connectivity_complete": True,
        },
    }
    result = review_physics(evidence)
    assert result["passed"] is True
    assert result["topology"]["junction_count"] == 2


def test_physics_flags_unphysical_impedance():
    evidence = {
        "device": "cpw",
        "sidecar": {"info": {"device_type": "cpw", "has_ground_plane": True, "impedance_ohm": 500},
                    "ports": [{"name": "in"}, {"name": "out"}]},
    }
    assert review_physics(evidence)["passed"] is False


# --- Microwave reviewer ---

def test_microwave_flags_passivity_violation_for_passive_device():
    evidence = {
        "device": "cpw",
        "sidecar": {"ports": [{"name": "in"}, {"name": "out"}]},
        "simulation": {"s_parameters_db": {"s11_db": -1.0, "s21_db": 3.0}},  # gain on a passive device
    }
    result = review_microwave(evidence)
    assert result["passed"] is False
    assert any("Passivity violated" in f["finding"] for f in result["findings"])


def test_microwave_allows_gain_for_active_jpa():
    evidence = {
        "device": "jpa",
        "sidecar": {"ports": [{"name": "rf_in"}, {"name": "rf_out"}]},
        "simulation": {"s_parameters_db": {"s11_db": -1.0, "s21_db": 20.0}},
    }
    result = review_microwave(evidence)
    assert result["passed"] is True  # active device: passivity not applied


# --- Fabrication reviewer ---

def test_fabrication_scores_drc_violations():
    clean = review_fabrication({"drc": {"status": "passed", "violations": []}})
    assert clean["passed"] is True and clean["tapeout_readiness"] == 100
    dirty = review_fabrication({"drc": {"violations": [
        {"rule": "min_width", "message": "too narrow", "severity": "error"}]}})
    assert dirty["passed"] is False and dirty["tapeout_readiness"] < 100


# --- Measurement reviewer ---

def test_measurement_flags_missing_pump_for_jpa():
    evidence = {"device": "jpa", "sidecar": {"ports": [{"name": "rf_in"}, {"name": "rf_out"}]}}
    result = review_measurement(evidence)
    assert any("pump/flux" in f["finding"] for f in result["findings"])


# --- Committee aggregation ---

def test_committee_min_score_blocks_on_any_error():
    evidence = {
        "device": "cpw",
        "sidecar": {"info": {"device_type": "cpw"}, "ports": [{"name": "in"}, {"name": "out"}]},
        "drc": {"status": "passed", "violations": []},
    }  # cpw without ground -> physics error
    committee = review_committee(evidence)
    assert committee["approved"] is False
    assert committee["score"] < 90
    assert committee["error_count"] >= 1


def test_committee_approves_clean_device():
    committee = review_committee(_good_cpw_evidence())
    assert committee["approved"] is True
    assert committee["score"] >= 90


# --- Auto-repair loop ---

def test_auto_repair_converges_and_terminates():
    def generate(state):
        return {
            "device": "cpw_resonator",
            "sidecar": {
                "info": {"device_type": "cpw_resonator", "has_ground_plane": state["has_ground"]},
                "ports": [{"name": "in"}, {"name": "out"}],
            },
            "drc": {"status": "passed", "violations": []},
        }

    def repair(state, committee):
        new_state = dict(state)
        if any("Z0 is undefined" in b["finding"] for b in committee["blockers"]):
            new_state["has_ground"] = True
        return new_state

    result = run_auto_repair({"has_ground": False}, generate, repair, threshold=90, max_iterations=5)
    assert result["accepted"] is True
    assert result["iterations"] == 2  # broken -> repaired
    assert result["final_score"] >= 90
    assert result["history"][0]["approved"] is False


def test_auto_repair_stops_when_unfixable():
    def generate(state):
        # CPW permanently missing ground; repair cannot help.
        return {"device": "cpw", "sidecar": {"info": {"device_type": "cpw"},
                                              "ports": [{"name": "in"}, {"name": "out"}]}}

    def repair(state, committee):
        return state  # no progress

    result = run_auto_repair({}, generate, repair, max_iterations=4)
    assert result["accepted"] is False
    assert result["iterations"] == 1  # stops immediately when repair stalls
