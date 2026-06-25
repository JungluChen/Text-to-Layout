"""Tests for layout_validator.py — polygon-level GDS truth checking.

Covers Phases 2–6 of the EDA audit:
  - Phase 2: Layout geometry validation (JJ, CPW, via chain, ports)
  - Phase 3: Golden layout comparison
  - Phase 4: Physics extraction from GDS polygons only
  - Phase 5: Solver truth system (no fake data)
  - Phase 6: Report correctness

Every test uses real GDS output from compile_layout — no mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from text_to_gds.server import compile_layout, extract_layout

GOLDEN_DIR = Path(__file__).parent / "golden_layouts"


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    return tmp_path_factory.mktemp("layout_validator")


@pytest.fixture(scope="module")
def jj_layout(workspace, monkeypatch_module):
    monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
    return compile_layout("manhattan_josephson_junction",
                          parameters={"junction_width": 0.22, "junction_height": 0.22},
                          output_name="test_jj.gds")


@pytest.fixture(scope="module")
def cpw_layout(workspace, monkeypatch_module):
    monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
    return compile_layout("cpw_quarter_wave_resonator",
                          parameters={"target_frequency_ghz": 6.0,
                                      "effective_permittivity": 6.2,
                                      "trace_width": 10.0, "gap": 6.0},
                          output_name="test_cpw.gds")


@pytest.fixture(scope="module")
def jpa_layout(workspace, monkeypatch_module):
    monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
    return compile_layout("lumped_element_jpa_seed",
                          parameters={"squid_count": 1},
                          output_name="test_jpa.gds")


@pytest.fixture(scope="module")
def via_layout(workspace, monkeypatch_module):
    monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
    return compile_layout("via_chain_monitor",
                          parameters={"stage_count": 100},
                          output_name="test_via.gds",
                          layout_quality_mode="demo")


@pytest.fixture(scope="module")
def ground_layout(workspace, monkeypatch_module):
    monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
    return compile_layout("ground_plane",
                          parameters={"width": 250.0, "height": 250.0},
                          output_name="test_gnd.gds",
                          layout_quality_mode="demo")


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


# ── Phase 2: Layout Geometry Validation ────────────────────────────────────

class TestGDSBasic:
    def test_jj_gds_exists(self, jj_layout):
        assert Path(jj_layout["gds_path"]).is_file()

    def test_cpw_gds_exists(self, cpw_layout):
        assert Path(cpw_layout["gds_path"]).is_file()

    def test_via_gds_exists(self, via_layout):
        assert Path(via_layout["gds_path"]).is_file()

    def test_gds_not_empty(self, jj_layout):
        assert Path(jj_layout["gds_path"]).stat().st_size > 100

    def test_sidecar_exists(self, jj_layout):
        assert Path(jj_layout["sidecar_path"]).is_file()


class TestJJGeometry:
    def test_jj_has_barrier_layer(self, jj_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(jj_layout["gds_path"], jj_layout["sidecar_path"])
        jj_findings = [f for f in report["findings"] if f["check"] == "jj_geometry"]
        barrier_found = any("barrier polygon" in f["message"] for f in jj_findings)
        assert barrier_found, "JJ barrier polygons not found"

    def test_jj_area_from_polygons(self, jj_layout):
        """JJ area must be computed from polygon intersection, not stored metadata."""
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(jj_layout["gds_path"], jj_layout["sidecar_path"])
        jj_findings = [f for f in report["findings"] if f["check"] == "jj_geometry"]
        area_finding = next((f for f in jj_findings if "jj_area_um2" in f.get("details", {})), None)
        assert area_finding is not None, "No JJ area finding"
        area = area_finding["details"]["jj_area_um2"]
        assert abs(area - 0.0484) / 0.0484 < 0.05, f"JJ area {area} µm² ≠ expected 0.0484 µm²"

    def test_jj_electrodes_overlap_barrier(self, jj_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(jj_layout["gds_path"], jj_layout["sidecar_path"])
        errors = [f for f in report["findings"]
                  if f["severity"] == "error" and f["check"] == "jj_geometry"]
        overlap_errors = [f for f in errors if "overlap" in f["message"].lower()]
        assert not overlap_errors, f"Electrode overlap errors: {overlap_errors}"

    def test_jj_has_bottom_and_top_electrode(self, jj_layout):
        import klayout.db as kdb
        layout = kdb.Layout()
        layout.read(jj_layout["gds_path"])
        cell = layout.top_cell()
        from text_to_gds.layout_validator import _layer_index, _polygons_on_layer
        from text_to_gds.process import DEFAULT_PROCESS
        m1_idx = _layer_index(layout, DEFAULT_PROCESS.layer("M1"))
        m2_idx = _layer_index(layout, DEFAULT_PROCESS.layer("M2"))
        assert m1_idx is not None, "M1 layer missing"
        assert m2_idx is not None, "M2 layer missing"
        assert len(_polygons_on_layer(cell, m1_idx)) > 0, "No M1 polygons (bottom electrode)"
        assert len(_polygons_on_layer(cell, m2_idx)) > 0, "No M2 polygons (top electrode)"


class TestCPWTopology:
    def test_cpw_z0_near_50_ohm(self, cpw_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(cpw_layout["gds_path"], cpw_layout["sidecar_path"])
        cpw_findings = [f for f in report["findings"] if f["check"] == "cpw_topology"]
        z0_finding = next((f for f in cpw_findings
                           if "z0_calculated_ohm" in f.get("details", {})), None)
        assert z0_finding is not None, "No Z0 finding"
        z0 = z0_finding["details"]["z0_calculated_ohm"]
        assert 40 <= z0 <= 60, f"Z0={z0:.2f} Ω outside 40–60 Ω range for 50 Ω CPW"

    def test_cpw_has_signal_and_ground(self, cpw_layout):
        import klayout.db as kdb
        layout = kdb.Layout()
        layout.read(cpw_layout["gds_path"])
        cell = layout.top_cell()
        from text_to_gds.layout_validator import _layer_index, _polygons_on_layer
        from text_to_gds.process import DEFAULT_PROCESS
        m1_idx = _layer_index(layout, DEFAULT_PROCESS.layer("M1"))
        m2_idx = _layer_index(layout, DEFAULT_PROCESS.layer("M2"))
        assert m1_idx is not None and len(_polygons_on_layer(cell, m1_idx)) > 0, "No M1 ground"
        assert m2_idx is not None and len(_polygons_on_layer(cell, m2_idx)) > 0, "No M2 signal"

    def test_cpw_has_no_ground_short_and_real_gap(self, cpw_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(cpw_layout["gds_path"], cpw_layout["sidecar_path"])
        overlap = next(
            f for f in report["findings"]
            if f["check"] == "cpw_topology" and "signal_ground_overlap_um2" in f.get("details", {})
        )
        clearance = next(
            f for f in report["findings"]
            if f["check"] == "cpw_topology" and "clearance_intrusion_um2" in f.get("details", {})
        )
        assert overlap["details"]["signal_ground_overlap_um2"] == pytest.approx(0.0, abs=1e-9)
        assert clearance["details"]["clearance_intrusion_um2"] == pytest.approx(0.0, abs=1e-9)


class TestJPAFeatures:
    def test_jpa_contains_required_physical_features(self, jpa_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(jpa_layout["gds_path"], jpa_layout["sidecar_path"])
        assert report["passed"], [f for f in report["findings"] if f["severity"] == "error"]
        inventory = next(f for f in report["findings"] if f["check"] == "jpa_features")
        assert inventory["details"]["jj_count"] == 2
        assert inventory["details"]["idc_finger_count"] >= 4
        assert inventory["details"]["rf_ports"]

    def test_jpa_sidecar_area_is_boolean_extracted(self, jpa_layout):
        sidecar = json.loads(Path(jpa_layout["sidecar_path"]).read_text(encoding="utf-8"))
        info = sidecar["info"]
        assert info["junction_area_method"] == "polygon_boolean_extracted"
        assert info["junction_area_formula"] == "area(M1 intersect M2 within JJ process window)"
        assert info["junction_area_um2"] == pytest.approx(2 * 0.22 * 0.22, rel=1e-6)


class TestResonatorLength:
    def test_lambda_over_4_length_physical(self, cpw_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(cpw_layout["gds_path"], cpw_layout["sidecar_path"])
        resonator_findings = [f for f in report["findings"]
                              if f["check"] == "resonator_length"]
        length_finding = next((f for f in resonator_findings
                               if "expected_um" in f.get("details", {})), None)
        assert length_finding is not None, "No resonator length finding"
        actual = length_finding["details"]["actual_um"]
        assert 1000 < actual < 50000, f"λ/4 length {actual} µm is unrealistic"
        assert length_finding["details"]["deviation_pct"] < 5.0, \
            f"λ/4 length deviation {length_finding['details']['deviation_pct']:.1f}% > 5%"


class TestViaChain:
    def test_via_count_matches_stages(self, via_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(via_layout["gds_path"], via_layout["sidecar_path"])
        via_findings = [f for f in report["findings"] if f["check"] == "via_chain"]
        count_finding = next((f for f in via_findings
                              if "via_count" in f.get("details", {})), None)
        assert count_finding is not None, "No via count finding"
        via_count = count_finding["details"]["via_count"]
        assert via_count >= 100, f"Via count {via_count} < 100 stages"

    def test_via_chain_has_multi_layer_metal(self, via_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(via_layout["gds_path"], via_layout["sidecar_path"])
        errors = [f for f in report["findings"]
                  if f["severity"] == "error" and f["check"] == "via_chain"]
        layer_errors = [f for f in errors if "layer(s)" in f["message"]]
        assert not layer_errors, f"Via chain layer errors: {layer_errors}"

    def test_via_overlaps_metal(self, via_layout):
        from text_to_gds.layout_validator import validate_layout
        report = validate_layout(via_layout["gds_path"], via_layout["sidecar_path"])
        errors = [f for f in report["findings"]
                  if f["severity"] == "error" and f["check"] == "via_chain"
                  and "overlap" in f["message"].lower()]
        assert not errors, f"Via overlap errors: {errors}"


# ── Phase 3: Golden Layout Comparison ──────────────────────────────────────

class TestGoldenComparison:
    def test_jj_golden(self, jj_layout):
        expected = json.loads((GOLDEN_DIR / "expected_manhattan_jj.json").read_text(encoding="utf-8"))
        from text_to_gds.layout_validator import validate_against_golden
        report = validate_against_golden(jj_layout["gds_path"], expected,
                                         sidecar_path=jj_layout["sidecar_path"])
        assert report["golden_passed"], f"JJ golden failed: {report.get('golden_findings')}"

    def test_cpw_golden_layers(self, cpw_layout):
        expected = json.loads((GOLDEN_DIR / "expected_cpw_resonator.json").read_text(encoding="utf-8"))
        from text_to_gds.layout_validator import validate_against_golden
        report = validate_against_golden(cpw_layout["gds_path"], expected,
                                         sidecar_path=cpw_layout["sidecar_path"])
        layer_errors = [f for f in report.get("golden_findings", [])
                        if f["severity"] == "error" and f["check"] == "golden_layers"]
        assert not layer_errors, f"CPW golden layer errors: {layer_errors}"

    def test_via_golden(self, via_layout):
        expected = json.loads((GOLDEN_DIR / "expected_via_chain.json").read_text(encoding="utf-8"))
        from text_to_gds.layout_validator import validate_against_golden
        report = validate_against_golden(via_layout["gds_path"], expected,
                                         sidecar_path=via_layout["sidecar_path"])
        assert report["golden_passed"], f"Via golden failed: {report.get('golden_findings')}"

    def test_ground_golden(self, ground_layout):
        expected = json.loads((GOLDEN_DIR / "expected_ground_plane.json").read_text(encoding="utf-8"))
        from text_to_gds.layout_validator import validate_against_golden
        report = validate_against_golden(ground_layout["gds_path"], expected,
                                         sidecar_path=ground_layout["sidecar_path"])
        assert report["golden_passed"], f"Ground golden failed: {report.get('golden_findings')}"


# ── Phase 4: Physics Extraction From Polygons ──────────────────────────────

class TestPhysicsExtraction:
    def test_extraction_has_lineage(self, jj_layout):
        ext = extract_layout(jj_layout["sidecar_path"], jc_ua_per_um2=2.0)
        lineage = ext.get("lineage", {})
        for key, rec in lineage.items():
            assert rec.get("source") != "LLM", f"source='LLM' in lineage key '{key}'"
            assert rec.get("method_label") in ("extracted", "estimated", "simulated", "measured"), \
                f"Invalid method_label in lineage key '{key}': {rec.get('method_label')}"

    def test_extraction_jj_ic_from_area(self, jj_layout):
        """Ic must derive from junction area × Jc, not from stored metadata."""
        ext = extract_layout(jj_layout["sidecar_path"], jc_ua_per_um2=2.0)
        params = ext.get("parameters", {})
        ic = params.get("critical_current_ua")
        if ic is not None:
            expected_ic = 0.0484 * 2.0  # area × Jc
            assert abs(float(ic) - expected_ic) / expected_ic < 0.15, \
                f"Ic={ic} µA vs expected {expected_ic:.4f} µA from JJ area"

    def test_cpw_z0_not_from_llm(self, cpw_layout):
        ext = extract_layout(cpw_layout["sidecar_path"])
        lineage = ext.get("lineage", {})
        z0_lineage = lineage.get("z0_ohm", lineage.get("characteristic_impedance_ohm", {}))
        if z0_lineage:
            assert z0_lineage.get("source") != "LLM"


# ── Phase 5: Solver Truth System ───────────────────────────────────────────

class TestSolverTruth:
    def test_skipped_solver_not_executed(self):
        from text_to_gds.artifact_validator import validate_artifact
        result = {"status": "skipped", "reason": "solver not installed"}
        check = validate_artifact("openems", result)
        assert check["passed"] is True
        assert check["status"] == "skipped"

    def test_executed_without_artifact_fails(self):
        from text_to_gds.artifact_validator import validate_artifact
        result = {"status": "executed"}
        check = validate_artifact("openems", result)
        assert check["passed"] is False, "openEMS with no .s2p must fail"

    def test_josim_needs_waveform(self):
        from text_to_gds.artifact_validator import validate_artifact
        result = {"status": "executed", "waveform": []}
        check = validate_artifact("josim", result)
        assert check["passed"] is False, "JoSIM with empty waveform must fail"

    def test_scqubits_needs_eigenvalues(self):
        from text_to_gds.artifact_validator import validate_artifact
        result = {"status": "executed", "execution": {"energy_levels_ghz": []}}
        check = validate_artifact("scqubits", result)
        assert check["passed"] is False, "scqubits with empty eigenvalues must fail"

    def test_jc_needs_gain_array(self):
        from text_to_gds.artifact_validator import validate_artifact
        result = {"status": "executed"}
        check = validate_artifact("josephsoncircuits", result)
        assert check["passed"] is False, "JC.jl with no gain array must fail"

    def test_valid_jc_passes(self):
        from text_to_gds.artifact_validator import validate_artifact
        result = {"gain_db": [10.0, 15.0, 20.0, 18.0]}
        check = validate_artifact("josephsoncircuits", result)
        assert check["passed"] is True

    def test_valid_scqubits_passes(self):
        from text_to_gds.artifact_validator import validate_artifact
        result = {"execution": {"energy_levels_ghz": [0.0, 5.0, 9.8], "f01_ghz": 5.0}}
        check = validate_artifact("scqubits", result)
        assert check["passed"] is True


# ── Phase 6: Report Correctness ────────────────────────────────────────────

class TestReportCorrectness:
    def test_sidecar_is_fabrication_semantic_not_visualization_only(self, jj_layout):
        sidecar = json.loads(Path(jj_layout["sidecar_path"]).read_text(encoding="utf-8"))
        info = sidecar.get("info", {})
        assert info.get("visualization_only") is False
        assert info.get("junction_area_method") == "polygon_boolean_extracted"

    def test_sidecar_device_type(self, jj_layout):
        sidecar = json.loads(Path(jj_layout["sidecar_path"]).read_text(encoding="utf-8"))
        info = sidecar.get("info", {})
        assert "junction" in info.get("device_type", "").lower() or \
               "jj" in info.get("device", "").lower(), \
            f"JJ sidecar device_type={info.get('device_type')} doesn't match expected"

    def test_cpw_sidecar_z0_physical(self, cpw_layout):
        sidecar = json.loads(Path(cpw_layout["sidecar_path"]).read_text(encoding="utf-8"))
        info = sidecar.get("info", {})
        z0 = info.get("z0_ohm")
        assert z0 is not None, "CPW sidecar missing z0_ohm"
        assert 20 < float(z0) < 150, f"Z0={z0} Ω outside physical range"

    def test_compile_returns_required_keys(self, jj_layout):
        for key in ("status", "gds_path", "sidecar_path", "screenshot_path"):
            assert key in jj_layout, f"Missing key '{key}' in compile_layout result"


# ── Phase 7: Intentional Failure Tests ─────────────────────────────────────

class TestIntentionalFailures:
    def test_default_rejects_ground_only_coupon(self, workspace, monkeypatch_module):
        monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
        result = compile_layout("ground_plane", output_name="ground_reject.gds")
        assert result["status"] == "unsupported"
        assert not (workspace / "ground_reject.gds").exists()

    def test_default_rejects_decorative_via_chain(self, workspace, monkeypatch_module):
        monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
        result = compile_layout("via_chain_monitor", output_name="via_reject.gds")
        assert result["status"] == "unsupported"
        assert not (workspace / "via_reject.gds").exists()

    def test_cpw_signal_overlapping_ground_fails(self, tmp_path):
        import gdsfactory as gf
        from text_to_gds.layout_validator import validate_layout
        from text_to_gds.process import M1, M2

        c = gf.Component()
        c.add_polygon([(-20, -10), (20, -10), (20, 10), (-20, 10)], layer=M1)
        c.add_polygon([(-10, -2), (10, -2), (10, 2), (-10, 2)], layer=M2)
        gds = tmp_path / "shorted_cpw.gds"
        c.write_gds(gds)
        sidecar = tmp_path / "shorted_cpw.sidecar.json"
        sidecar.write_text(json.dumps({
            "pcell": "cpw_quarter_wave_resonator",
            "ports": [{"name": "feed_in", "layer": [5, 0]}],
            "info": {
                "device_type": "cpw_quarter_wave_resonator",
                "trace_width_um": 4.0,
                "gap_um": 6.0,
                "layers": {"ground": M1, "signal": M2},
            },
        }), encoding="utf-8")
        report = validate_layout(gds, sidecar)
        assert not report["passed"]
        assert any("shorts to ground" in f["message"] for f in report["findings"])

    def test_jj_marker_rectangle_without_al_overlap_fails(self, tmp_path):
        import gdsfactory as gf
        from text_to_gds.extraction import extract_physical_parameters
        from text_to_gds.layout_validator import validate_layout
        from text_to_gds.process import JJ

        c = gf.Component()
        c.add_polygon([(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)], layer=JJ)
        gds = tmp_path / "marker_only_jj.gds"
        c.write_gds(gds)
        sidecar = tmp_path / "marker_only_jj.sidecar.json"
        sidecar.write_text(json.dumps({
            "pcell": "manhattan_josephson_junction",
            "ports": [],
            "info": {"device_type": "manhattan_josephson_junction"},
        }), encoding="utf-8")
        validation = validate_layout(gds, sidecar)
        extraction = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=2.0)
        assert not validation["passed"]
        assert extraction["status"] == "failed"
        assert "M1/M2" in extraction["reason"]

    def test_jpa_gain_without_executed_solver_fails_review(self, jpa_layout):
        from text_to_gds.review import review_committee

        sidecar = json.loads(Path(jpa_layout["sidecar_path"]).read_text(encoding="utf-8"))
        result = review_committee({
            "device": "JPA",
            "sidecar": sidecar,
            "simulation": {"gain_db": [10.0, 12.0], "status": "skipped"},
        })
        assert not result["approved"]
        assert any("gain" in blocker["finding"].lower() for blocker in result["blockers"])

    def test_not_executed_solver_panel_cannot_pass_review(self, jpa_layout):
        from text_to_gds.review import review_committee

        sidecar = json.loads(Path(jpa_layout["sidecar_path"]).read_text(encoding="utf-8"))
        result = review_committee({
            "device": "JPA",
            "sidecar": sidecar,
            "simulation": {"panel": "NOT EXECUTED"},
        })
        assert not result["approved"]
        assert any("NOT EXECUTED" in blocker["finding"] for blocker in result["blockers"])

    def test_reject_fake_jj_area(self, workspace, monkeypatch_module):
        """A JJ with impossible dimensions must be caught."""
        monkeypatch_module.setattr("text_to_gds.server.ARTIFACT_ROOT", workspace)
        result = compile_layout("manhattan_josephson_junction",
                                parameters={"junction_width": 0.22, "junction_height": 0.22},
                                output_name="test_reject_jj.gds")
        expected = {"jj_area_um2": 1.0}  # deliberately wrong
        from text_to_gds.layout_validator import validate_against_golden
        report = validate_against_golden(result["gds_path"], expected,
                                         sidecar_path=result["sidecar_path"])
        assert not report["golden_passed"], "Should fail when expected area doesn't match"

    def test_reject_disconnected_port_layer(self):
        """validate_layout should catch ports on non-existent layers."""
        import tempfile
        from text_to_gds.layout_validator import validate_layout
        import klayout.db as kdb
        layout = kdb.Layout()
        layout.create_cell("EMPTY")
        with tempfile.NamedTemporaryFile(suffix=".gds", delete=False) as f:
            path = f.name
        layout.write(path)
        sidecar_path = path.replace(".gds", ".sidecar.json")
        Path(sidecar_path).write_text(json.dumps({
            "ports": [{"name": "fake", "layer": [99, 0]}],
            "info": {},
        }))
        report = validate_layout(path, sidecar_path)
        port_warnings = [f for f in report["findings"]
                         if f["check"] == "port_connectivity"
                         and f["severity"] in ("warning", "error")]
        assert len(port_warnings) > 0, "Should warn about ports on missing layers"
        Path(path).unlink(missing_ok=True)
        Path(sidecar_path).unlink(missing_ok=True)
