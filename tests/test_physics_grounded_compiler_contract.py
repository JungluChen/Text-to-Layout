from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from text_to_gds.extraction import extract_physical_parameters
from text_to_gds.pcells import (
    cpw_quarter_wave_resonator,
    lumped_element_jpa_seed,
    manhattan_josephson_junction,
)
from text_to_gds.simulation.solver_adapter import BaseSolverAdapter


def _write(component: Any, path: Path) -> Path:
    component.write_gds(path)
    return path


def test_manhattan_jj_is_process_aware_and_extracted_from_gds(tmp_path):
    component = manhattan_josephson_junction(
        junction_width=0.24,
        junction_height=0.20,
        lead_width=0.8,
        electrode_length=7.0,
    )
    assert component.info["device"] == "manhattan_jj"
    assert component.info["fabrication"]["process"] == "double_angle_evaporation"
    assert component.info["layers"]["bottom_electrode"] != component.info["layers"]["top_electrode"]

    gds = _write(component, tmp_path / "jj.gds")
    sidecar = {
        "pcell": "manhattan_josephson_junction",
        "gds_path": str(gds),
        "info": dict(component.info),
        "ports": [],
    }
    extracted = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=2.0)

    assert extracted["status"] == "ok"
    assert extracted["geometry"]["manhattan_jj"]["junction_area_um2"] == pytest.approx(0.048)
    assert extracted["geometry"]["manhattan_jj"]["top_electrode_width"] == pytest.approx(0.8)
    assert extracted["geometry"]["manhattan_jj"]["bottom_electrode_width"] == pytest.approx(0.2)


def test_extracted_numbers_have_required_lineage_fields(tmp_path):
    component = manhattan_josephson_junction(junction_width=0.24, junction_height=0.20)
    gds = _write(component, tmp_path / "jj_lineage.gds")
    result = extract_physical_parameters(
        gds,
        {"pcell": "manhattan_josephson_junction", "info": dict(component.info)},
        jc_ua_per_um2=2.0,
    )

    required = {"value", "unit", "method_label", "source", "formula", "confidence"}
    for key, record in result["lineage"].items():
        assert required <= set(record), key
        assert record["method_label"] in {
            "geometry_extracted",
            "analytical",
            "simulated",
            "measured",
        }


def test_cpw_resonator_carries_conformal_mapping_lineage():
    component = cpw_quarter_wave_resonator(
        target_frequency_ghz=6.0,
        trace_width=10.0,
        gap=6.0,
        effective_permittivity=6.2,
    )
    info = component.info
    assert 45.0 < info["z0_ohm"] < 55.0
    assert info["phase_velocity_m_per_s"] > 0.0
    assert info["lambda_over_4_resonance_hz"] == pytest.approx(6.0e9, rel=1e-6)
    assert info["lineage"]["z0_ohm"]["formula"].startswith("Z0 =")
    assert info["lineage"]["lambda_over_4_resonance_hz"]["formula"] == "f0 = vp/(4*l)"


def test_lumped_jpa_maps_layout_to_equivalent_circuit():
    component = lumped_element_jpa_seed(center_frequency_ghz=6.0, squid_count=3)
    circuit = component.info["equivalent_circuit"]

    assert component.info["squid_junction_count"] == 6
    assert {"C", "Lj(phi)", "Cc", "Z0"} <= set(circuit)
    assert circuit["C"]["value"] > 0.0
    assert circuit["Cc"]["value"] > 0.0
    assert circuit["Lj(phi)"]["junction_count"] == 6


class MissingSolver(BaseSolverAdapter):
    def __init__(self) -> None:
        super().__init__(solver_name="DummySolver", executable="missing")

    def is_available(self) -> bool:
        return False

    def _generate_input(self, input_data: dict[str, Any], *, output_dir: Path) -> Path:
        raise AssertionError("should not generate input when unavailable")

    def _run_solver(self, input_path: Path) -> None:
        raise AssertionError("should not run when unavailable")

    def _parse_output(self, output_path: Path) -> dict[str, Any]:
        raise AssertionError("should not parse when unavailable")

    def _validate_output(self, parsed: dict[str, Any]) -> bool:
        return False


def test_solver_boundary_uses_strict_uppercase_status(tmp_path):
    result = MissingSolver().execute({}, output_dir=tmp_path).to_dict()

    assert result["status"] == "SKIPPED"
    assert result["solver"] == "DummySolver"
    assert result["input_file"] is None
    assert result["output_file"] is None
    assert "Solver unavailable" in result["reason"]
