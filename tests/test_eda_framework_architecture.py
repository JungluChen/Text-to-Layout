from __future__ import annotations

from pathlib import Path

from text_to_gds.components import MicrowaveComponent, JosephsonComponent, QuantumComponent
from text_to_gds.device_library import JPA, Resonator, Transmon
from text_to_gds.optimization.closed_loop import optimize_jpa_closed_loop
from text_to_gds.pdk import (
    DEFAULT_LAYER_MAP,
    DEFAULT_MANHATTAN_PROCESS,
    DEFAULT_MATERIAL_CATALOG,
    DEFAULT_TECHNOLOGY,
    FabricationRuleSet,
)
from text_to_gds.reference_compare import compare_cpw_against_references
from text_to_gds.routing import RouteCPW, RouteSpec
from text_to_gds.simulation.backends import OpenEMSBackend
from text_to_gds.synthesis import synthesize_jpa, synthesize_resonator, synthesize_transmon


ROOT = Path(__file__).resolve().parents[1]


def test_pdk_package_exposes_materials_layers_rules_and_technology():
    assert DEFAULT_MATERIAL_CATALOG.nb.penetration_depth_nm > 0
    assert DEFAULT_MATERIAL_CATALOG.alox.nominal_jc_ua_per_um2 > 0
    assert DEFAULT_LAYER_MAP.cpw_center_trace == (5, 0)
    assert DEFAULT_MANHATTAN_PROCESS.jj_min_area == 0.01
    assert DEFAULT_TECHNOLOGY.process.bottom_layer == "M1"
    assert isinstance(DEFAULT_MANHATTAN_PROCESS.rules, FabricationRuleSet)


def test_component_base_classes_and_device_methods():
    devices = [Transmon(), JPA(), Resonator()]
    assert isinstance(devices[0], JosephsonComponent)
    assert isinstance(devices[1], JosephsonComponent)
    assert isinstance(devices[2], MicrowaveComponent)
    for device in devices:
        assert isinstance(device, QuantumComponent)
        assert device.geometry().ports
        assert device.ports()
        assert device.netlist().nets
        extraction = device.extract()
        assert extraction["schema"].startswith("text-to-gds.device.extract")
        assert device.simulate()["status"] == "skipped"


def test_routing_engine_supports_snapping_length_and_collision_check():
    route = RouteCPW().build(
        RouteSpec(
            start_um=(0.2, 0.2),
            end_um=(100.2, 40.2),
            target_length_um=180.0,
            snap_um=1.0,
            bend_radius_um=30.0,
        )
    )
    assert route.length_um >= 180.0
    assert route.bend_radius_um == 30.0
    assert route.collision_free is True
    assert route.metadata["impedance_preserving"] is True


def test_synthesis_outputs_physical_parameters():
    resonator = synthesize_resonator(frequency_ghz=6.0)
    jpa = synthesize_jpa(frequency_ghz=6.0, target_gain_db=20.0, bandwidth_mhz=200.0)
    transmon = synthesize_transmon(frequency_ghz=5.0, anharmonicity_mhz=-250.0)
    assert 20.0 < resonator["impedance_ohm"] < 150.0
    assert jpa["capacitance_ff"] > 0
    assert jpa["junction_area_um2"] > 0
    assert transmon["ej_over_ec"] > 10.0


def test_simulation_backend_lifecycle_prepares_without_fake_execution(tmp_path):
    backend = OpenEMSBackend()
    prepared = backend.prepare({"device": "cpw"}, tmp_path)
    assert prepared.status == "input_files_prepared"
    assert Path(prepared.prepared_files[0]).is_file()
    run = backend.run(prepared)
    assert run.status == "skipped"
    assert "solver not executed" in run.reason


def test_closed_loop_reports_skipped_without_solver_callback():
    result = optimize_jpa_closed_loop()
    assert result["status"] == "skipped"
    assert result["initial_design"]["frequency_ghz"] == 6.0


def test_reference_comparison_uses_cloned_stack(tmp_path):
    report = compare_cpw_against_references(project_root=ROOT, output_dir=tmp_path)
    assert report["schema"] == "text-to-gds.reference-comparison.v1"
    assert Path(report["report_path"]).is_file()
    assert Path(report["image_path"]).is_file()
    assert any(item["available"] for item in report["comparisons"])
