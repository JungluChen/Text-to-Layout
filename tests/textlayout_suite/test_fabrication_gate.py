"""DRC gives NOT_FABRICATION_READY its first producer.

The status existed in the vocabulary, enforced by the model and emitted by
nothing. Here DRC emits it -- by *demoting* a physics claim, never by disputing
it. A minimum-spacing violation says nothing about whether the resonance was
computed correctly, and a clean DRC says nothing about whether it was either.
"""

from __future__ import annotations

from pathlib import Path

import klayout.db as kdb
import pytest

from textlayout.evidence import ConfidenceClass, EvidenceStatus
from textlayout.evidence.canonical import (
    CanonicalEvidence,
    ConvergenceMetrics,
    sha256_file,
)
from textlayout.pdk.fabrication_gate import apply_fabrication_gate
from textlayout.pdk.klayout_drc import run_drc
from textlayout.pdk.models import PDK, PDKGrid, PDKLayer, PDKSubstrate


def _pdk(**overrides) -> PDK:
    payload = {
        "name": "gate_pdk", "version": "1.0", "foundry_validated": True,
        "calibration_status": "foundry_calibrated", "source": "test fixture",
        "grid": PDKGrid(grid_nm=1.0, default_min_spacing_um=1.0, default_min_width_um=1.0),
        "substrate": PDKSubstrate(material="Si", epsilon_r=11.9, loss_tangent=1e-6),
        "layers": [
            PDKLayer(name="M1", purpose="metal", gds_layer=1, min_width_um=1.0, min_spacing_um=2.0)
        ],
    }
    payload.update(overrides)
    return PDK(**payload)  # type: ignore[arg-type]


def _gds(tmp_path: Path, boxes: list[kdb.Box], layer: int = 1) -> Path:
    layout = kdb.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    index = layout.layer(layer, 0)
    for box in boxes:
        top.shapes(index).insert(box)
    path = tmp_path / "gate.gds"
    layout.write(str(path))
    return path


def _um(value: float) -> int:
    return int(round(value * 1000))


@pytest.fixture
def verified(tmp_path: Path) -> CanonicalEvidence:
    output = tmp_path / "eig.csv"
    output.write_text("m,Re{f} (GHz)\n1,6.0\n", encoding="utf-8")
    return CanonicalEvidence(
        evidence_id="abc123",
        design_id="resonator",
        design_hash="d" * 64,
        component="quarter_wave_resonator",
        analysis_scope="eigenmode",
        target_quantity="eigenmode_frequency",
        target_value=6.0,
        target_unit="GHz",
        extracted_quantity="eigenmode_frequency",
        extracted_value=6.0015,
        extracted_unit="GHz",
        error_percent=0.025,
        tolerance_percent=0.5,
        status=EvidenceStatus.PHYSICS_VERIFIED,
        solver_name="Palace",
        solver_version="0.16.0",
        container_digest="sha256:" + "c" * 64,
        parser="p",
        parser_version="1",
        output_file_hashes={"eig.csv": sha256_file(output)},
        extraction_config={"mode": 1},
        extraction_config_hash="e" * 64,
        convergence=ConvergenceMetrics(
            method="mesh_refinement", refinement_levels=3, delta_percent=0.07,
            threshold_percent=0.5, converged=True,
        ),
        timestamp="2026-07-10T00:00:00+00:00",
    )


class TestABlockedDesignIsDemoted:
    def test_a_drc_violation_blocks_a_physics_verified_claim(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(0.4), _um(5))])  # narrower than 1 um
        gated = apply_fabrication_gate(verified, run_drc(_pdk(), gds))

        assert gated.status is EvidenceStatus.NOT_FABRICATION_READY
        assert gated.confidence_class is ConfidenceClass.NONE
        assert "min_width" in (gated.blocking_reason or "")

    def test_the_extracted_value_survives_because_it_was_never_disputed(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        """A minimum-spacing violation says nothing about the eigenfrequency."""
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(0.4), _um(5))])
        gated = apply_fabrication_gate(verified, run_drc(_pdk(), gds))
        assert gated.extracted_value == 6.0015
        assert gated.solver_name == "Palace"

    def test_the_withdrawn_permission_is_recorded_as_superseded(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(0.4), _um(5))])
        gated = apply_fabrication_gate(verified, run_drc(_pdk(), gds))
        assert gated.superseded is not None
        assert gated.superseded.status == "PHYSICS_VERIFIED"
        assert gated.superseded.extracted_value == 6.0015
        assert "may not be taped out" in gated.superseded.why_withdrawn
        assert gated.supersedes_evidence_id == "abc123"

    def test_the_gds_becomes_an_artifact_dependency(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(0.4), _um(5))])
        report = run_drc(_pdk(), gds)
        gated = apply_fabrication_gate(verified, report)
        edge = next(d for d in gated.depends_on if d.role == "drc_input_gds")
        assert edge.sha256 == report.gds_sha256

    def test_the_unchecked_rules_are_carried_into_the_warnings(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(0.4), _um(5))])
        gated = apply_fabrication_gate(verified, run_drc(_pdk(), gds))
        assert any("rules not implemented" in w for w in gated.warnings)
        assert any("antenna_ratio" in w for w in gated.warnings)


class TestBlockingIsBroaderThanViolations:
    def test_an_illustrative_pdk_blocks_even_a_clean_layout(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        pdk = _pdk(foundry_validated=False, calibration_status="illustrative")
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(5), _um(5))])
        report = run_drc(pdk, gds)
        assert report.passed  # every rule is satisfied...
        gated = apply_fabrication_gate(verified, report)
        assert gated.status is EvidenceStatus.NOT_FABRICATION_READY  # ...and it still blocks
        assert "illustrative" in (gated.blocking_reason or "")

    def test_undeclared_geometry_blocks(self, verified: CanonicalEvidence, tmp_path: Path) -> None:
        layout = kdb.Layout()
        layout.dbu = 0.001
        top = layout.create_cell("TOP")
        top.shapes(layout.layer(1, 0)).insert(kdb.Box(0, 0, _um(5), _um(5)))
        top.shapes(layout.layer(42, 0)).insert(kdb.Box(0, 0, _um(5), _um(5)))
        path = tmp_path / "gate.gds"
        layout.write(str(path))

        gated = apply_fabrication_gate(verified, run_drc(_pdk(), path))
        assert gated.status is EvidenceStatus.NOT_FABRICATION_READY
        assert "does not declare" in (gated.blocking_reason or "")


class TestACleanDrcChangesNothing:
    def test_a_signoff_ready_run_leaves_the_record_untouched(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(5), _um(5))])
        report = run_drc(_pdk(), gds)
        assert report.signoff_ready
        assert apply_fabrication_gate(verified, report) is verified

    def test_a_clean_drc_cannot_promote_an_unverified_claim(
        self, verified: CanonicalEvidence, tmp_path: Path
    ) -> None:
        """Passing design rules says nothing about whether the physics is right."""
        executed = verified.model_copy(
            update={"status": EvidenceStatus.SIMULATION_EXECUTED, "error_percent": 40.0}
        )
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(5), _um(5))])
        gated = apply_fabrication_gate(executed, run_drc(_pdk(), gds))
        assert gated.status is EvidenceStatus.SIMULATION_EXECUTED

    def test_gating_is_idempotent(self, verified: CanonicalEvidence, tmp_path: Path) -> None:
        gds = _gds(tmp_path, [kdb.Box(0, 0, _um(0.4), _um(5))])
        report = run_drc(_pdk(), gds)
        once = apply_fabrication_gate(verified, report)
        twice = apply_fabrication_gate(once, report)
        assert twice is once
