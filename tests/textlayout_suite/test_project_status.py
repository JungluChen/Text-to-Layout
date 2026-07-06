"""scripts/generate_project_status.py schema v2 + the new claim-gate checks.

Sprint 1 (status consistency): the manifest must introspect the *real* CLI,
record EPR/measurement support honestly, and the claim checker must reject
hard-coded test counts and stale manifests. Complements
test_project_claims.py, which covers the v1 checks (PHYSICS_VERIFIED
cross-checks, fabrication language, version drift).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

EXPECTED_COMMANDS = {
    "prompt",
    "generate",
    "verify",
    "epr",
    "doctor",
    "serve",
    "yield",
    "chip",
    "pdk",
    "measurement",
}

EXPECTED_EPR_STATUSES = {
    "EPR_ANALYTICAL_ONLY",
    "EPR_EXECUTED",
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def status_module():
    return _load("generate_project_status_v2", SCRIPTS_DIR / "generate_project_status.py")


@pytest.fixture()
def claims_module():
    return _load("check_project_claims_v2", SCRIPTS_DIR / "check_project_claims.py")


class TestStatusManifestSchema:
    def test_schema_is_v2_with_all_sections(self, status_module) -> None:
        status = status_module.build_status()
        assert status["schema"] == "textlayout.project-status.v2"
        for key in (
            "package_version",
            "cli_commands",
            "showcase",
            "test_report",
            "known_limitations",
            "pdk_status",
            "epr_support",
            "measurement_support",
        ):
            assert key in status, key

    def test_cli_commands_are_introspected_not_hand_listed(self, status_module) -> None:
        commands = status_module._cli_commands()
        assert EXPECTED_COMMANDS <= set(commands)
        assert commands["yield"] == ["jj", "qubit-array"]
        assert commands["chip"] == ["analyze", "optimize"]
        assert commands["measurement"] == ["calibrate", "compare"]

    def test_epr_support_is_honest_about_default_backend(self, status_module) -> None:
        epr = status_module._epr_support(status_module._cli_commands())
        assert epr["cli_command"] is True
        assert epr["field_solver_verified_by_default"] is False
        assert EXPECTED_EPR_STATUSES <= set(epr["statuses"])

    def test_measurement_support_declares_fixtures_synthetic(self, status_module) -> None:
        meas = status_module._measurement_support(status_module._cli_commands())
        assert meas["compare_command"] is True
        assert meas["calibrate_command"] is True
        assert meas["fixtures_are_synthetic"] is True


class TestHardcodedTestCountGate:
    def _run(self, claims_module, tmp_path: Path, text: str) -> list[str]:
        (tmp_path / "CURRENT_STATUS.md").write_text(text, encoding="utf-8")
        claims_module.ROOT = tmp_path
        errors: list[str] = []
        claims_module.check_no_hardcoded_test_counts(errors)
        return errors

    def test_hardcoded_count_fails(self, claims_module, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors = self._run(claims_module, tmp_path, "All good: 726 passed, 0 failed.\n")
        assert errors and "hard-coded test count" in errors[0]

    def test_stale_history_mention_is_allowed(self, claims_module, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors = self._run(
            claims_module,
            tmp_path,
            'The old snapshot went stale (it claimed "726 passed, 0 failed").\n',
        )
        assert errors == []

    def test_pointer_to_generated_status_is_allowed(
        self, claims_module, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors = self._run(
            claims_module, tmp_path, "See PROJECT_STATUS.md for live numbers.\n"
        )
        assert errors == []


class TestStatusManifestFreshness:
    def _write_repo(self, tmp_path: Path, manifest: dict) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.3.0"\ndescription = "textlayout"\n',
            encoding="utf-8",
        )
        out = tmp_path / "out" / "evidence"
        out.mkdir(parents=True)
        (out / "project_status.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_wrong_schema_fails(self, claims_module, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        self._write_repo(
            tmp_path, {"schema": "textlayout.project-status.v1", "package_version": "0.3.0"}
        )
        errors: list[str] = []
        claims_module.check_status_manifest_freshness(errors)
        assert errors and "schema" in errors[0]

    def test_version_drift_fails(self, claims_module, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        self._write_repo(
            tmp_path,
            {"schema": "textlayout.project-status.v2", "package_version": "0.1.0"},
        )
        errors: list[str] = []
        claims_module.check_status_manifest_freshness(errors)
        assert errors and "package_version" in errors[0]

    def test_stale_cli_command_list_fails(self, claims_module, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        self._write_repo(
            tmp_path,
            {
                "schema": "textlayout.project-status.v2",
                "package_version": "0.3.0",
                "cli_commands": {"prompt": [], "removed-command": []},
            },
        )
        errors: list[str] = []
        claims_module.check_status_manifest_freshness(errors)
        assert errors and "cli_commands" in errors[0]

    def test_absent_manifest_is_not_an_error(self, claims_module, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.3.0"\ndescription = "textlayout"\n',
            encoding="utf-8",
        )
        errors: list[str] = []
        claims_module.check_status_manifest_freshness(errors)
        assert errors == []

    def test_current_repo_manifest_is_fresh(self, claims_module) -> None:
        """The committed workflow (generate then check) must hold for this repo."""
        errors: list[str] = []
        claims_module.check_status_manifest_freshness(errors)
        assert errors == []
