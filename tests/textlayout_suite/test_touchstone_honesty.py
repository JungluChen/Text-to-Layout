"""Sprint 3: NaN Touchstone data and sweep-edge extrema can never become claims.

Both cases are real, committed failure modes, not hypotheticals:

- showcase 05's openEMS run injected zero port energy for 250k timesteps
  ("Energy: ~0.00e+00" throughout), wrote an all-NaN .s2p, and the old parser
  turned that into "resonance = 3.0 GHz" — exactly the sweep start.
- the old notch/peak chooser preferred a monotonic ramp's edge maximum over a
  genuine interior notch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from textlayout.simulation import SimulationResult, run_openems
from textlayout.simulation.sparameters import find_resonance_frequency, read_sparameters


def _write_s2p(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join(["# GHz S RI R 50", *rows]) + "\n", encoding="utf-8")
    return path


def _nan_s2p(path: Path, n: int = 20) -> Path:
    rows = [
        f"{3.0 + i * 0.1:.3f} nan nan nan nan nan nan nan nan" for i in range(n)
    ]
    return _write_s2p(path, rows)


def _monotonic_s2p(path: Path, n: int = 41) -> Path:
    # |S21| ramps monotonically: resonance-free data.
    rows = [
        f"{3.0 + i * 0.1:.3f} 0.1 0 {0.2 + i * 0.015:.4f} 0 {0.2 + i * 0.015:.4f} 0 0.1 0"
        for i in range(n)
    ]
    return _write_s2p(path, rows)


class TestNanRejection:
    def test_read_sparameters_rejects_nan(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            read_sparameters(_nan_s2p(tmp_path / "nan.s2p"))

    def test_run_openems_reports_failed_not_executed(self, tmp_path: Path) -> None:
        """The exact showcase-05 incident: NaN data must yield FAILED, no number."""
        s2p = _nan_s2p(tmp_path / "openems_result.s2p")
        prepared = SimulationResult(
            status="input_files_prepared",
            solver="openEMS",
            readiness_level=2,
            reason="prepared",
            output_dir=tmp_path,
            artifacts={},
        )
        result = run_openems(prepared, target_frequency_ghz=6.0, touchstone=s2p)
        assert result.status == "failed"
        assert result.physics_verified is False
        assert result.extracted_quantities == {}
        assert "non-finite" in result.reason

    def test_partial_nan_is_also_rejected(self, tmp_path: Path) -> None:
        rows = [
            "3.0 0.1 0 0.9 0 0.9 0 0.1 0",
            "4.0 nan nan 0.9 0 0.9 0 0.1 0",
            "5.0 0.1 0 0.9 0 0.9 0 0.1 0",
        ]
        with pytest.raises(ValueError, match="1/3"):
            read_sparameters(_write_s2p(tmp_path / "partial.s2p", rows))


class TestSweepEdgeRejection:
    def test_monotonic_data_has_no_resonance(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="sweep edge"):
            find_resonance_frequency(_monotonic_s2p(tmp_path / "ramp.s2p"))

    def test_interior_notch_beats_edge_peak(self, tmp_path: Path) -> None:
        # Ramp with a genuine notch at 5.0 GHz: the edge maximum must lose.
        rows = []
        for i in range(41):
            f = 3.0 + i * 0.1
            mag = 0.2 + i * 0.015
            if abs(f - 5.0) < 0.05:
                mag = 0.01
            rows.append(f"{f:.3f} 0.1 0 {mag:.4f} 0 {mag:.4f} 0 0.1 0")
        found = find_resonance_frequency(_write_s2p(tmp_path / "notch.s2p", rows))
        assert found == pytest.approx(5.0e9)

    def test_run_openems_edge_artifact_is_failed(self, tmp_path: Path) -> None:
        s2p = _monotonic_s2p(tmp_path / "openems_result.s2p")
        prepared = SimulationResult(
            status="input_files_prepared",
            solver="openEMS",
            readiness_level=2,
            reason="prepared",
            output_dir=tmp_path,
            artifacts={},
        )
        result = run_openems(prepared, target_frequency_ghz=6.0, touchstone=s2p)
        assert result.status == "failed"
        assert result.physics_verified is False
