"""Sprint 2: every EPR report carries PDK provenance; PDK inputs never
upgrade the honesty status.

Covers the pdk_bridge (name/path resolution, substrate override, provenance
hash), the CLI default (`textlayout epr` writes evidence with generic_2metal
provenance when no --pdk is given), and the failure path for an unknown PDK.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from textlayout.cli import main as cli_main
from textlayout.epr import (
    DEFAULT_PDK_NAME,
    materials_db_from_pdk,
    render_markdown,
    resolve_pdk_path,
)
from textlayout.epr.backends import AnalyticalEPRBackend
from textlayout.knowledge.technology_library import PDKS_DIR
from textlayout.schemas.dsl import LayoutSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
IDC_SPEC = REPO_ROOT / "examples" / "idc_0p6pf.json"


def _spec() -> LayoutSpec:
    return LayoutSpec.model_validate(json.loads(IDC_SPEC.read_text(encoding="utf-8")))


class TestPdkBridge:
    def test_resolve_registered_name(self) -> None:
        path = resolve_pdk_path(DEFAULT_PDK_NAME)
        assert path.is_file()
        assert path.parent == PDKS_DIR

    def test_resolve_explicit_path(self) -> None:
        explicit = PDKS_DIR / "example_superconducting_pdk.yaml"
        assert resolve_pdk_path(str(explicit)) == explicit

    def test_unknown_pdk_raises_with_available_names(self) -> None:
        with pytest.raises(FileNotFoundError, match="registered"):
            resolve_pdk_path("no-such-pdk")

    def test_substrate_channel_comes_from_pdk(self) -> None:
        db, provenance = materials_db_from_pdk("example_superconducting_pdk")
        from textlayout.pdk import load_pdk

        pdk = load_pdk(PDKS_DIR / "example_superconducting_pdk.yaml")
        substrate = db.channel("substrate")
        assert substrate.tan_delta == pdk.substrate.loss_tangent
        assert substrate.epsilon_r == pdk.substrate.epsilon_r
        assert provenance.pdk_name == pdk.name

    def test_file_hash_is_byte_exact(self) -> None:
        path = resolve_pdk_path(DEFAULT_PDK_NAME)
        _, provenance = materials_db_from_pdk(DEFAULT_PDK_NAME)
        assert provenance.file_hash_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()

    def test_interface_channels_stay_literature_scaled(self) -> None:
        """A PDK YAML has no MS/SA/MA loss tangents; inventing them = fake physics."""
        from textlayout.epr import illustrative_silicon_db

        base = illustrative_silicon_db()
        db, _ = materials_db_from_pdk("example_superconducting_pdk")
        for name in ("metal_substrate", "substrate_air", "metal_air"):
            assert db.channel(name).tan_delta == base.channel(name).tan_delta


class TestHonestyIsNotUpgraded:
    def test_pdk_materials_do_not_change_epr_status(self) -> None:
        db, _ = materials_db_from_pdk("example_superconducting_pdk")
        result = AnalyticalEPRBackend().analyze(_spec(), frequency_ghz=6.0, materials=db)
        assert result.status == "EPR_ANALYTICAL_ONLY"

    def test_markdown_report_states_not_foundry_calibrated(self) -> None:
        db, provenance = materials_db_from_pdk(DEFAULT_PDK_NAME)
        result = AnalyticalEPRBackend().analyze(_spec(), frequency_ghz=6.0, materials=db)
        result = result.model_copy(
            update={"pdk_provenance": provenance.model_dump(mode="json")}
        )
        markdown = render_markdown(result)
        assert "PDK provenance" in markdown
        assert provenance.file_hash_sha256 in markdown
        assert "NOT foundry-calibrated" in markdown


class TestEprCli:
    def test_default_run_attaches_generic_2metal_provenance(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = cli_main(["epr", str(IDC_SPEC), "--out", str(tmp_path)])
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "EPR_ANALYTICAL_ONLY"
        pdk = payload["pdk_provenance"]
        assert pdk["pdk_name"] == "generic_2metal_pdk"
        assert pdk["calibration_status"] == "illustrative"
        assert len(pdk["file_hash_sha256"]) == 64
        report = json.loads((tmp_path / "epr_report.json").read_text(encoding="utf-8"))
        assert report["pdk_provenance"]["file_hash_sha256"] == pdk["file_hash_sha256"]
        assert (tmp_path / "epr_report.md").is_file()

    def test_explicit_pdk_changes_substrate_assumptions(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = cli_main(
            [
                "epr",
                str(IDC_SPEC),
                "--pdk",
                "example_superconducting_pdk",
                "--out",
                str(tmp_path),
            ]
        )
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["pdk_provenance"]["pdk_name"] == "example_superconducting_pdk"

    def test_unknown_pdk_fails_cleanly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = cli_main(
            ["epr", str(IDC_SPEC), "--pdk", "no-such-pdk", "--out", str(tmp_path)]
        )
        assert exit_code == 2
        payload = json.loads(capsys.readouterr().out)
        assert "no-such-pdk" in payload["error"]
        assert not (tmp_path / "epr_report.json").exists()

    def test_verify_include_epr_carries_pdk_provenance(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = cli_main(["verify", str(IDC_SPEC), "--include-epr"])
        assert exit_code in (0, 2)  # geometry verdict is not under test here
        payload = json.loads(capsys.readouterr().out)
        assert payload["epr"]["pdk_provenance"]["pdk_name"] == "generic_2metal_pdk"
        assert payload["epr"]["status"] == "EPR_ANALYTICAL_ONLY"
