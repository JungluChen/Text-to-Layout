"""PDK schema, YAML loading, Technology conversion, DRC hooks, LVS honesty."""

from __future__ import annotations

import json

import pytest
import yaml

from textlayout.knowledge.technology_library import (
    GENERIC_2METAL,
    PDKS_DIR,
    default_technology_library,
)
from textlayout.pdk import (
    PDK,
    NotImplementedLVSChecker,
    STATUS_SKIPPED_NOT_IMPLEMENTED,
    Netlist,
    NetlistDevice,
    PDKGrid,
    PDKLayer,
    PDKSubstrate,
    check_density,
    check_layer_exists,
    load_pdk,
    pdk_to_technology,
    write_pdk,
)

BUILT_IN_PDKS = sorted(PDKS_DIR.glob("*.yaml"))


def _minimal_pdk(**overrides) -> PDK:
    defaults = dict(
        name="test_pdk",
        version="0.0.1",
        foundry_validated=False,
        source="unit test fixture",
        grid=PDKGrid(grid_nm=1.0, default_min_spacing_um=1.0, default_min_width_um=1.0),
        substrate=PDKSubstrate(material="Si", epsilon_r=11.9, loss_tangent=1e-6),
        layers=[
            PDKLayer(
                name="M1",
                purpose="metal",
                gds_layer=1,
                min_width_um=1.0,
                min_spacing_um=1.0,
                max_density_fraction=0.8,
                min_density_fraction=0.1,
            ),
        ],
    )
    defaults.update(overrides)
    return PDK(**defaults)


class TestPDKSchema:
    def test_duplicate_layer_names_rejected(self) -> None:
        with pytest.raises(Exception):
            _minimal_pdk(
                layers=[
                    PDKLayer(
                        name="M1",
                        purpose="metal",
                        gds_layer=1,
                        min_width_um=1.0,
                        min_spacing_um=1.0,
                    ),
                    PDKLayer(
                        name="M1",
                        purpose="metal",
                        gds_layer=2,
                        min_width_um=1.0,
                        min_spacing_um=1.0,
                    ),
                ]
            )

    def test_duplicate_gds_numbers_rejected(self) -> None:
        with pytest.raises(Exception):
            _minimal_pdk(
                layers=[
                    PDKLayer(
                        name="M1",
                        purpose="metal",
                        gds_layer=1,
                        min_width_um=1.0,
                        min_spacing_um=1.0,
                    ),
                    PDKLayer(
                        name="M2",
                        purpose="metal",
                        gds_layer=1,
                        min_width_um=1.0,
                        min_spacing_um=1.0,
                    ),
                ]
            )

    def test_invalid_purpose_rejected(self) -> None:
        with pytest.raises(Exception):
            PDKLayer(
                name="X", purpose="not_a_purpose", gds_layer=1, min_width_um=1.0, min_spacing_um=1.0
            )

    def test_density_bounds_must_be_ordered(self) -> None:
        with pytest.raises(Exception):
            PDKLayer(
                name="M1",
                purpose="metal",
                gds_layer=1,
                min_width_um=1.0,
                min_spacing_um=1.0,
                min_density_fraction=0.9,
                max_density_fraction=0.1,
            )

    def test_layer_lookup(self) -> None:
        pdk = _minimal_pdk()
        assert pdk.layer("M1").gds_layer == 1
        with pytest.raises(KeyError):
            pdk.layer("GHOST")

    def test_summary_contains_provenance(self) -> None:
        pdk = _minimal_pdk()
        summary = pdk.summary()
        assert summary == {
            "pdk_name": "test_pdk",
            "pdk_version": "0.0.1",
            "foundry_validated": False,
            "calibration_status": "illustrative",
            "source": "unit test fixture",
        }


class TestBuiltInPDKs:
    @pytest.mark.parametrize("path", BUILT_IN_PDKS, ids=[p.stem for p in BUILT_IN_PDKS])
    def test_built_in_pdk_loads_and_is_not_foundry_validated(self, path) -> None:
        pdk = load_pdk(path)
        assert pdk.foundry_validated is False, (
            f"{pdk.name} claims foundry_validated=True; no shipped PDK may claim this"
        )
        assert pdk.layers

    def test_at_least_generic_and_superconducting_examples_exist(self) -> None:
        names = {p.stem for p in BUILT_IN_PDKS}
        assert "generic_2metal" in names
        assert "example_superconducting_pdk" in names


class TestLoaderRoundtrip:
    def test_yaml_roundtrip(self, tmp_path) -> None:
        pdk = _minimal_pdk()
        path = write_pdk(pdk, tmp_path / "roundtrip.yaml")
        loaded = load_pdk(path)
        assert loaded == pdk

    def test_json_supported(self, tmp_path) -> None:
        pdk = _minimal_pdk()
        path = tmp_path / "pdk.json"
        path.write_text(json.dumps(pdk.model_dump(mode="json")), encoding="utf-8")
        loaded = load_pdk(path)
        assert loaded.name == pdk.name

    def test_unsupported_extension_rejected(self, tmp_path) -> None:
        path = tmp_path / "pdk.txt"
        path.write_text("irrelevant", encoding="utf-8")
        with pytest.raises(ValueError):
            load_pdk(path)

    def test_malformed_yaml_raises_validation_error(self, tmp_path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.safe_dump({"name": "incomplete"}), encoding="utf-8")
        with pytest.raises(Exception):
            load_pdk(path)


class TestPdkToTechnology:
    def test_conversion_preserves_layer_rules(self) -> None:
        pdk = _minimal_pdk()
        tech = pdk_to_technology(pdk)
        assert tech.name == "test_pdk"
        assert tech.has_layer("M1")
        assert tech.min_width_for("M1") == 1.0
        assert tech.substrate_epsilon_r == 11.9

    def test_conversion_is_usable_as_a_real_technology(self) -> None:
        """A PDK-derived Technology must satisfy the same interface real generators use."""
        pdk = _minimal_pdk()
        tech = pdk_to_technology(pdk)
        assert tech.layer("M1").gds_layer == 1
        assert tech.min_spacing_for("UNKNOWN_LAYER") == tech.default_min_spacing_um


class TestTechnologyLibraryIntegration:
    def test_generic_2metal_unchanged_by_pdk_autoload(self) -> None:
        library = default_technology_library()
        tech = library.get("generic_2metal")
        assert tech is GENERIC_2METAL  # exact same hardcoded object, not reconstructed

    def test_example_superconducting_pdk_is_auto_registered(self) -> None:
        library = default_technology_library()
        assert "example_superconducting_pdk" in library.names()
        tech = library.get("example_superconducting_pdk")
        assert tech.has_layer("JJ")
        assert tech.has_layer("M3")


class TestDensityDRC:
    def test_no_rule_configured_is_a_noop_pass(self) -> None:
        pdk = _minimal_pdk(
            layers=[
                PDKLayer(
                    name="M1", purpose="metal", gds_layer=1, min_width_um=1.0, min_spacing_um=1.0
                )
            ]
        )
        result = check_density(pdk, "M1", filled_fraction=0.99)
        assert result.passed

    def test_within_bounds_passes(self) -> None:
        pdk = _minimal_pdk()
        result = check_density(pdk, "M1", filled_fraction=0.5)
        assert result.passed

    def test_too_sparse_fails(self) -> None:
        pdk = _minimal_pdk()
        result = check_density(pdk, "M1", filled_fraction=0.05)
        assert not result.passed
        assert "below minimum" in result.message

    def test_too_dense_fails(self) -> None:
        pdk = _minimal_pdk()
        result = check_density(pdk, "M1", filled_fraction=0.95)
        assert not result.passed
        assert "above maximum" in result.message

    def test_out_of_range_fraction_rejected(self) -> None:
        pdk = _minimal_pdk()
        with pytest.raises(ValueError):
            check_density(pdk, "M1", filled_fraction=1.5)

    def test_layer_exists_check(self) -> None:
        pdk = _minimal_pdk()
        assert check_layer_exists(pdk, "M1")
        assert not check_layer_exists(pdk, "GHOST")


class TestLVSHonesty:
    def test_not_implemented_checker_never_claims_match(self) -> None:
        reference = Netlist(
            name="ref",
            devices=[NetlistDevice(ref="C1", device_type="capacitor", nodes=["P1", "P2"])],
            nets=["P1", "P2"],
        )
        extracted = Netlist(name="extracted", devices=[], nets=[])
        report = NotImplementedLVSChecker().compare(reference, extracted)
        assert report.status == STATUS_SKIPPED_NOT_IMPLEMENTED
        assert report.status not in ("MATCH", "MISMATCH")
