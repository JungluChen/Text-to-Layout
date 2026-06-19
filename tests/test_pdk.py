from __future__ import annotations

from pathlib import Path

import pytest

from text_to_gds.pdk import PDKDatabase, SuperconductingPDK, load_pdk
from text_to_gds.server import inspect_process_design_kit, list_process_design_kits


ROOT = Path(__file__).resolve().parents[1]


def test_all_shipped_pdks_load_and_convert_to_existing_process_model():
    pdks = PDKDatabase(ROOT / "process").list()
    assert {pdk.process_id for pdk in pdks} == {
        "custom_process",
        "ibm_nb",
        "mit_ll_sfq",
        "ncu_alox_2026",
    }
    for pdk in pdks:
        assert pdk.layers
        assert pdk.materials
        assert pdk.to_process_stack().name.endswith(f"@{pdk.version}")


def test_pdk_layer_mapping_rules_and_surface_impedance():
    pdk = load_pdk(ROOT / "process" / "NCU_AlOx_2026.yaml")
    assert pdk.layer_for_gds(4).purpose == "Josephson tunnel junction"
    assert pdk.validate_geometry("JJ", width_um=0.05, spacing_um=0.1) == [
        "JJ width 0.05 um is below 0.1 um",
        "JJ spacing 0.1 um is below 0.2 um",
    ]
    impedance = pdk.materials["Al"].surface_impedance(6e9)
    assert impedance["resistance_ohm_per_square"] > 0.0
    assert impedance["reactance_ohm_per_square"] > 0.0


def test_database_selects_latest_semantic_version(tmp_path):
    source = (ROOT / "process" / "custom_process.yaml").read_text(encoding="utf-8")
    (tmp_path / "v1.yaml").write_text(source.replace("version: 0.1.0", "version: 1.0.0"))
    (tmp_path / "v2.yaml").write_text(source.replace("version: 0.1.0", "version: 1.2.0"))
    assert PDKDatabase(tmp_path).get("custom_process").version == "1.2.0"
    assert PDKDatabase(tmp_path).get("custom_process", "1.0.0").version == "1.0.0"


def test_pdk_rejects_undefined_material_and_duplicate_gds_mapping():
    data = {
        "schema": "text-to-gds.superconducting-pdk.v1",
        "process_id": "bad",
        "name": "Bad fixture",
        "version": "1.0.0",
        "status": "test",
        "materials": {"Nb": {"kind": "superconductor"}},
        "layers": {
            "M1": {
                "gds": [1, 0],
                "purpose": "wire",
                "material": "missing",
                "thickness_nm": 100,
                "min_width_um": 0.2,
                "min_spacing_um": 0.2,
                "overlay_tolerance_um": 0.1,
            }
        },
        "constraints": {
            "min_junction_width_um": 0.1,
            "min_junction_height_um": 0.1,
            "min_trace_width_um": 0.2,
            "min_trace_spacing_um": 0.2,
            "min_cpw_gap_um": 1.0,
            "via_min_size_um": 0.3,
            "via_enclosure_um": 0.2,
            "overlay_tolerance_um": 0.1,
        },
    }
    with pytest.raises(ValueError, match="undefined materials"):
        SuperconductingPDK.from_dict(data)


def test_pdk_mcp_tools_return_json_serializable_models():
    listing = list_process_design_kits()
    assert listing["schema"] == "text-to-gds.process-design-kits.v1"
    inspection = inspect_process_design_kit("ncu_alox_2026", material="Al")
    assert inspection["process_design_kit"]["version"] == "1.0.0"
    assert inspection["surface_impedance"]["reactance_ohm_per_square"] > 0.0
