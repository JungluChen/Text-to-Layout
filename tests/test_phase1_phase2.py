"""Phase 1 (1.3/1.4/1.6) and Phase 2 (templates + feasibility gate) tests."""

from __future__ import annotations

from text_to_gds.em_solvers import get_em_solver, list_em_solvers
from text_to_gds.feasibility_gate import check_design_feasibility
from text_to_gds.meep_bridge import meep_available, write_meep_project
from text_to_gds.open_q3d import OpenQ3D, tune_idc_capacitance
from text_to_gds.open_solver_manager import open_eigenmode
from text_to_gds.pcells import manhattan_josephson_junction
from text_to_gds.physics_templates import list_templates, load_template, validate_sidecar


# --- 1.6 MEEP ---

def test_meep_registered_and_open_source():
    names = {entry["name"] for entry in list_em_solvers()}
    assert "MEEP" in names
    assert get_em_solver("MEEP").open_source is True


def test_meep_project_writes_script_and_skips_without_binary(tmp_path):
    result = write_meep_project(
        tmp_path / "dev.gds",
        script_path=tmp_path / "dev.meep.py",
        report_path=tmp_path / "dev.meep.json",
        run=True,
    )
    assert (tmp_path / "dev.meep.py").exists()
    expected = "executed" if meep_available() else "skipped"
    # run=True with no meep -> skipped; prepared only when not running.
    assert result["status"] in {expected, "prepared"}


# --- 1.3 open eigenmode (HFSS-equivalent schema) ---

def test_open_eigenmode_emits_hfss_schema(tmp_path):
    gds = tmp_path / "jj.gds"
    manhattan_josephson_junction().write_gds(str(gds))
    result = open_eigenmode(gds, output_stem=tmp_path / "jj", run=False)
    for key in ("frequency", "Q", "participation", "fields", "convergence"):
        assert key in result
    assert result["hfss_equivalent_schema"] == ["frequency", "Q", "participation", "fields", "convergence"]
    assert result["status"] in {"prepared", "skipped"}


# --- 1.4 OpenQ3D ---

def test_open_q3d_extract_schema(tmp_path):
    gds = tmp_path / "jj.gds"
    manhattan_josephson_junction().write_gds(str(gds))
    result = OpenQ3D().extract(gds, output_stem=tmp_path / "jj", run=False)
    assert result["schema"] == "text-to-gds.open-q3d.v1"
    assert "matrix_pf" in result["capacitance"]
    assert "inductance_nh" in result["inductance"]
    assert "available" in result["coupling"]


def test_idc_auto_tune_converges_within_tolerance():
    result = tune_idc_capacitance(0.6, tolerance_pct=1.0)
    assert result["within_tolerance"] is True
    assert result["error_pct"] <= 1.0
    assert abs(result["achieved_pf"] - 0.6) < 0.006
    assert result["geometry"]["finger_count"] >= 2


# --- 2.1 physics templates ---

def test_templates_listed_and_loadable():
    templates = list_templates()
    assert {"cpw", "resonator", "jpa", "jtwpa", "sfq", "transmon"} <= set(templates)
    jpa = load_template("JPA")
    assert jpa["device"] == "JPA"
    assert "junction" in jpa["must_have"]
    assert "bode_fano" in jpa["constraints"]


def test_template_match_by_substring():
    assert load_template("cpw_resonator")["template_name"] in {"cpw", "resonator"}


def test_validate_sidecar_reports_features():
    sidecar = {
        "pcell": "lumped_element_jpa_seed",
        "info": {"device_type": "jpa_squid"},
        "ports": [{"name": "rf_in"}, {"name": "rf_out"}],
    }
    report = validate_sidecar(sidecar, "JPA")
    assert report["device"] == "JPA"
    assert "junction" in report["satisfied"]  # detected via 'squid' in device text
    assert "input_port" in report["satisfied"]


# --- 2.2 feasibility gate ---

def test_feasibility_rejects_gain_bandwidth_violation():
    result = check_design_feasibility(
        "JPA", {"gain_db": 20, "bandwidth_mhz": 2000, "frequency_ghz": 6.0}
    )
    assert result["accepted"] is False
    assert result["verdict"] == "infeasible"
    assert any("bode_fano" in b for b in result["blockers"])


def test_feasibility_accepts_reasonable_spec():
    result = check_design_feasibility(
        "JPA", {"gain_db": 10, "bandwidth_mhz": 200, "frequency_ghz": 6.0, "quality_factor": 10}
    )
    assert result["accepted"] is True
    assert result["verdict"] == "feasible"


def test_feasibility_flags_out_of_range_frequency():
    result = check_design_feasibility("transmon", {"frequency_ghz": 50.0})
    assert result["accepted"] is False
    assert any(v["parameter"] == "frequency_ghz" for v in result["range_violations"])


def test_feasibility_unknown_device_still_runs_constraints():
    result = check_design_feasibility("mystery", {"gain_db": 10, "bandwidth_mhz": 100})
    assert result["template"] is None
    assert result["template_warning"] is not None
    assert "constraint_report" in result
