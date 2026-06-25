"""Phase 4-6 tests: layout understanding, open benchmarks, readiness, orchestration."""

from __future__ import annotations

from text_to_gds.ai_scientist import assess_design, write_review_report
from text_to_gds.layout_understanding import layout_novelty, summarize_layout
from text_to_gds.open_benchmarks import run_open_benchmarks
from text_to_gds.pcells import manhattan_josephson_junction
from text_to_gds.research_readiness import research_readiness
from text_to_gds.review.committee import review_committee


def _good_cpw_evidence():
    return {
        "device": "cpw_resonator",
        "sidecar": {
            "pcell": "cpw_quarter_wave_resonator",
            "layout_quality_mode": "fabrication_real",
            "quality_record": {"status": "supported"},
            "info": {"device_type": "cpw_resonator", "has_ground_plane": True},
            "ports": [{"name": "in"}, {"name": "out"}],
        },
        "drc": {"status": "passed", "violations": []},
        "extraction": {"status": "ok", "geometry": {}},
        "simulation": {"status": "SKIPPED", "reason": "no solver installed"},
        "layout_validation": {"passed": True, "findings": []},
        "literature_comparison": {
            "references": ["reference-cpw"],
            "comparisons": [{"parameter": "frequency_ghz", "generated": 6.0, "reference": 6.0}],
        },
    }


# --- Phase 4: layout understanding ---

def test_summarize_layout_detects_junction(tmp_path):
    gds = tmp_path / "jj.gds"
    manhattan_josephson_junction().write_gds(str(gds))
    summary = summarize_layout(gds, sidecar={"pcell": "manhattan_josephson_junction"})
    assert summary["device_class"] == "josephson_junction"
    assert summary["junction_count"] >= 1
    assert "josephson_junction" in summary["element_kinds"]
    assert len(summary["feature_vector"]) == 3


def test_layout_novelty_without_corpus_is_honest():
    result = layout_novelty([1.0, 2.0, 3.0])
    assert result["corpus_size"] == 0
    assert result["novelty_pct"] is None


def test_layout_novelty_with_corpus_ranks_and_scores():
    corpus = [{"name": "identical", "vector": [1.0, 2.0, 3.0]}, {"name": "other", "vector": [3.0, 0.0, 0.0]}]
    result = layout_novelty([1.0, 2.0, 3.0], corpus)
    assert result["corpus_size"] == 2
    assert result["matches"][0]["name"] == "identical"
    assert result["matches"][0]["similarity_pct"] == 100.0
    assert result["novelty_pct"] == 0.0


# --- Phase 5: functional benchmarks ---

def test_open_benchmarks_assert_physics_not_files():
    suite = run_open_benchmarks()
    by_id = {b["id"]: b for b in suite["benchmarks"]}
    # CPW: designed Z0 within 5% of 50 ohm and f0 within 5% of 6 GHz.
    cpw = by_id["01_CPW"]
    assert cpw["status"] == "passed"
    assert abs(cpw["computed"]["impedance_ohm"] - 50.0) / 50.0 <= 0.05
    assert abs(cpw["computed"]["frequency_ghz"] - 6.0) / 6.0 <= 0.05
    # IDC: 0.6 pF within 1%.
    assert by_id["02_IDC"]["status"] == "passed"
    # JPA: skipped without Julia (never a false pass).
    assert by_id["03_JPA"]["status"] == "skipped"
    assert suite["counts"]["failed"] == 0


def test_benchmarks_have_numeric_targets_and_computed():
    for bench in run_open_benchmarks()["benchmarks"]:
        assert "target" in bench and isinstance(bench["target"], dict)
        # Every non-skipped benchmark compares a computed quantity to a target.
        if bench["status"] != "skipped":
            assert isinstance(bench["computed"], dict) and bench["computed"]


# --- Phase 6.2: research readiness ---

def test_research_readiness_ready_when_all_axes_pass():
    committee = review_committee(_good_cpw_evidence())
    agreement = {"passed": True, "confidence_pct": 96.0}
    feasibility = {"accepted": True}
    readiness = research_readiness(committee, feasibility=feasibility, solver_agreement=agreement)
    assert readiness["ready"] is True
    assert readiness["gated"] is False
    assert readiness["aggregate"] >= 90


def test_research_readiness_gated_by_failing_axis():
    bad = {
        "device": "cpw",
        "sidecar": {"info": {"device_type": "cpw"}, "ports": [{"name": "in"}, {"name": "out"}]},
        "drc": {"status": "passed", "violations": []},
    }
    committee = review_committee(bad)  # cpw without ground -> physics error
    readiness = research_readiness(committee, feasibility={"accepted": True})
    assert readiness["ready"] is False
    assert readiness["gated"] is True


# --- Phase 6.3: orchestration ---

def test_assess_design_validates_feasible_candidate():
    result = assess_design("cpw", {"frequency_ghz": 6.0}, _good_cpw_evidence())
    assert result["stage"] == "review"
    assert result["accepted"] is True
    assert result["verdict"] == "validated"


def test_assess_design_rejects_infeasible_before_review():
    result = assess_design(
        "JPA", {"gain_db": 20, "bandwidth_mhz": 2000, "frequency_ghz": 6.0}, _good_cpw_evidence()
    )
    assert result["stage"] == "feasibility"
    assert result["accepted"] is False
    assert result["committee"] is None


def test_write_review_report(tmp_path):
    assessment = assess_design("cpw", {"frequency_ghz": 6.0}, _good_cpw_evidence())
    report = write_review_report(assessment, tmp_path / "review.md")
    assert report["report_path"].endswith("review.md")
    assert (tmp_path / "review.md").exists()
    assert "Verdict" in (tmp_path / "review.md").read_text(encoding="utf-8")
