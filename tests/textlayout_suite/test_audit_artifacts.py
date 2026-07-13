"""Regression tests for scripts/generate_audit_artifacts.py."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate_audit_artifacts.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("generate_audit_artifacts_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_audit_artifacts_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def audit_module():
    return _load_audit_module()


def test_actual_commit_discovery_accepts_head(audit_module) -> None:
    head = audit_module.git_stdout("rev-parse", "HEAD")
    observation = audit_module.repository_observation(head)
    assert observation["local_head"] == head
    assert observation["expected_start_valid"] is True
    assert "pre_edit_observation" not in observation


def test_wrong_expected_commit_fails_clearly(audit_module) -> None:
    observation = audit_module.repository_observation("0" * 40)
    assert observation["expected_start_valid"] is False
    assert "neither" in observation["expected_start_error"]


def test_fail_on_claim_downgrade_returns_nonzero(audit_module, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_module, "tool_inventory", lambda: {"tools": []})
    monkeypatch.setattr(audit_module, "run_record", lambda repository: {"repository": repository})
    monkeypatch.setattr(
        audit_module,
        "capability_matrix",
        lambda tools, run_payload: {"capabilities": [], "tools": tools},
    )
    monkeypatch.setattr(
        audit_module,
        "claim_audit",
        lambda: {
            "schema": "textlayout.audit.claim-audit.v2",
            "claims": [{"downgrade_required": True}],
        },
    )

    rc = audit_module.main(["--out", str(tmp_path), "--fail-on-claim-downgrade"])

    assert rc == 1
    assert (tmp_path / "claim_audit.json").is_file()


def test_deterministic_manifest_has_no_run_fields(audit_module) -> None:
    observation = audit_module.repository_observation()
    first = audit_module.deterministic_manifest(observation)
    second = audit_module.deterministic_manifest(observation)
    assert first == second
    encoded = json.dumps(first)
    assert "timestamp" not in encoded.lower()
    assert "duration_seconds" not in encoded
    assert str(REPO_ROOT) not in encoded
    assert all(not Path(row["path"]).is_absolute() for row in first["repository_files"])


def test_run_record_redacts_paths(audit_module, tmp_path) -> None:
    raw = f"{REPO_ROOT}\\x {Path.home()}\\secret C:\\Users\\someone\\tool.exe"
    redacted = audit_module.redact_string(raw)
    assert str(REPO_ROOT) not in redacted
    assert str(Path.home()) not in redacted
    assert "someone" not in redacted
    assert "$REPO" in redacted


def test_timeout_and_failed_command_recording(audit_module) -> None:
    timeout = audit_module.run_command([sys.executable, "-c", "import time; time.sleep(2)"], timeout=1)
    assert timeout.timed_out is True
    failed = audit_module.run_command([sys.executable, "-c", "raise SystemExit(7)"], timeout=5)
    assert failed.return_code == 7


def test_absent_docker_daemon_is_not_a_pass(audit_module) -> None:
    docker = audit_module.docker_commands()
    if docker["docker_ps"]["return_code"] != 0:
        assert docker["docker_ps"]["return_code"] != 0
        assert "stdout_sha256" in docker["docker_ps"]


def test_python_package_absent_and_present_probes(audit_module) -> None:
    present = audit_module.probe_python_package("json", "pip")
    assert present["present"] is True
    absent = audit_module.probe_python_package("definitely_absent_textlayout_pkg", "absent")
    assert absent["present"] is False


def _package_probe(
    *,
    spec_present: bool,
    metadata_present: bool,
    import_success: bool,
    version_matches_expected: bool | None = None,
) -> dict[str, object]:
    return {
        "spec_present": spec_present,
        "metadata_present": metadata_present,
        "import_success": import_success,
        "distribution_version": "1.0" if metadata_present else None,
        "version_matches_expected": version_matches_expected,
    }


def test_disabled_reference_tool_state(audit_module) -> None:
    state, notes = audit_module.external_tool_state(
        {"id": "pyepr", "license_review": "manual"},
        {"pyepr": {"checksum_verified": True}},
        None,
        None,
        None,
    )
    assert state == "DISABLED_REFERENCE_ONLY"
    assert notes


def test_python_launcher_does_not_make_absent_package_installed(audit_module) -> None:
    state, notes = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        _package_probe(spec_present=False, metadata_present=False, import_success=False),
        "C:\\Windows\\py.exe",
        None,
    )
    assert state == "LICENSE_REVIEWED"
    assert any("spec absent" in note for note in notes)


def test_python_package_in_different_interpreter_is_not_installed(audit_module) -> None:
    state, _notes = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        _package_probe(spec_present=False, metadata_present=False, import_success=False),
        "C:\\other-python\\python.exe",
        None,
    )
    assert state == "LICENSE_REVIEWED"


def test_python_package_spec_without_metadata_is_not_installed(audit_module) -> None:
    state, notes = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        _package_probe(spec_present=True, metadata_present=False, import_success=True),
        None,
        None,
    )
    assert state == "LICENSE_REVIEWED"
    assert any("metadata/version absent" in note for note in notes)


def test_python_package_import_failure_stops_at_installed(audit_module) -> None:
    state, notes = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        _package_probe(spec_present=True, metadata_present=True, import_success=False),
        None,
        None,
    )
    assert state == "INSTALLED"
    assert any("import failed" in note for note in notes)


def test_python_package_import_success_verifies_identity(audit_module) -> None:
    state, notes = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        _package_probe(spec_present=True, metadata_present=True, import_success=True),
        None,
        None,
    )
    assert state == "IDENTITY_VERIFIED"
    assert any("version identity succeeded" in note for note in notes)


def test_python_package_version_mismatch_stops_at_installed(audit_module) -> None:
    state, notes = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        _package_probe(
            spec_present=True,
            metadata_present=True,
            import_success=True,
            version_matches_expected=False,
        ),
        None,
        None,
    )
    assert state == "INSTALLED"
    assert any("does not match" in note for note in notes)


def test_absent_external_tool_stops_at_license_review(audit_module) -> None:
    state, _ = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        None,
        None,
        None,
    )
    assert state == "LICENSE_REVIEWED"


def test_external_executable_identity_only(audit_module) -> None:
    result = audit_module.CommandResult(["tool", "--version"], 0, "1.0", "", False, 0.01)
    state, _ = audit_module.external_tool_state(
        {"id": "demo", "license_review": "reviewed"},
        {"demo": {"checksum_verified": True}},
        None,
        "C:\\tool.exe",
        result,
    )
    assert state == "IDENTITY_VERIFIED"


def test_claim_downgrade_required_for_current_showcase_physics_claim(audit_module) -> None:
    claim = (
        "**PHYSICS_VERIFIED** "
        "`01_idc_0p6pf` - target agreement and historical solver output."
    )
    computed, passed, missing, replacement = audit_module.evaluate_claim(claim)
    assert computed != "PHYSICS_VERIFIED"
    assert missing
    assert "target_tolerance_passed" in replacement
    assert any("finite parsed output" in gate for gate in passed)


def test_restoring_old_showcase_physics_verified_string_fails_gate(
    audit_module, tmp_path, monkeypatch
) -> None:
    old_public_claim = (
        "| 01_idc_0p6pf capacitance | 0.600000 pF | 0.598641 pF | "
        "0.227% | `PHYSICS_VERIFIED` |"
    )
    computed, _passed, missing, _replacement = audit_module.evaluate_claim(old_public_claim)
    assert computed == "NUMERICALLY_CONVERGED"
    assert missing

    monkeypatch.setattr(audit_module, "tool_inventory", lambda: {"tools": []})
    monkeypatch.setattr(audit_module, "run_record", lambda repository: {"repository": repository})
    monkeypatch.setattr(
        audit_module,
        "capability_matrix",
        lambda tools, run_payload: {"capabilities": [], "tools": tools},
    )
    monkeypatch.setattr(
        audit_module,
        "claim_audit",
        lambda: {
            "schema": "textlayout.audit.claim-audit.v2",
            "claims": [{"claim_text": old_public_claim, "downgrade_required": True}],
        },
    )

    assert audit_module.main(["--out", str(tmp_path), "--fail-on-claim-downgrade"]) == 1


def test_claim_not_downgraded_when_all_physics_gates_pass(audit_module) -> None:
    record = {
        "solver_executable_sha256": "abc",
        "container_digest": None,
        "return_code": 0,
        "command": ["solver"],
        "output_file_hashes": {"out": "hash"},
        "extracted_value": 1.0,
        "sanity_checks": [{"name": "finite", "passed": True}],
        "convergence": {"converged": True},
        "analytical_model": "independent model",
        "solver_execution_environment_hash": "solver",
        "evidence_generation_environment_hash": "evidence",
    }
    level, _passed, missing = audit_module.physics_evidence_level(record)
    assert level == "PHYSICS_VERIFIED"
    assert missing == []


def test_mutated_physics_evidence_downgrades(audit_module) -> None:
    record = {
        "solver_executable_sha256": "abc",
        "return_code": 0,
        "command": ["solver"],
        "output_file_hashes": {"out": "hash"},
        "extracted_value": 1.0,
        "sanity_checks": [{"name": "finite", "passed": True}],
        "convergence": {"converged": True},
        "analytical_model": "independent model",
        "solver_execution_environment_hash": "solver",
        "evidence_generation_environment_hash": "evidence",
    }
    record.pop("solver_executable_sha256")
    level, _passed, missing = audit_module.physics_evidence_level(record)
    assert level != "PHYSICS_VERIFIED"
    assert "solver identity hash or immutable container digest" in missing


def test_capability_level_from_real_gate_files(audit_module) -> None:
    tools = {"tools": [{"id": "klayout", "current_state": "LICENSE_REVIEWED"}]}
    matrix = audit_module.capability_matrix(tools, {"container_runtime": {"docker_ps": {"return_code": 1}}})
    core = next(row for row in matrix["capabilities"] if row["capability"] == "core wheel and CLI")
    assert core["computed_level"] in audit_module.CAPABILITY_LEVELS
    assert core["evidence_hashes"]


def _capability(audit_module, gates):
    return audit_module.capability_result(
        "test capability",
        gates,
        "a" * 40,
    )


def test_integration_evidence_without_identity_is_rejected(audit_module) -> None:
    result = _capability(
        audit_module,
        [
            audit_module.Gate("implemented", "IMPLEMENTED", True),
            audit_module.Gate("identity verified", "IDENTITY_VERIFIED", False),
            audit_module.Gate("integration evidence", "INTEGRATION_TEST_PASSED", True),
        ],
    )
    assert result["computed_level"] == "IMPLEMENTED"
    assert result["first_failed_mandatory_gate"]["gate"] == "identity verified"
    assert result["consistency_errors"][0]["type"] == "non_monotonic_gate"


def test_benchmark_evidence_without_integration_is_rejected(audit_module) -> None:
    result = _capability(
        audit_module,
        [
            audit_module.Gate("implemented", "IMPLEMENTED", True),
            audit_module.Gate("integration", "INTEGRATION_TEST_PASSED", False),
            audit_module.Gate("benchmark", "BENCHMARK_EXECUTED", True),
        ],
    )
    assert result["computed_level"] == "IMPLEMENTED"
    assert result["consistency_errors"][0]["gate"] == "benchmark"


def test_numerical_validation_without_benchmark_is_rejected(audit_module) -> None:
    result = _capability(
        audit_module,
        [
            audit_module.Gate("benchmark", "BENCHMARK_EXECUTED", False),
            audit_module.Gate("numerical validation", "NUMERICALLY_VALIDATED", True),
        ],
    )
    assert result["computed_level"] == "NOT_IMPLEMENTED"
    assert result["consistency_errors"][0]["gate"] == "numerical validation"


def test_scientific_validation_without_independent_reference_is_rejected(audit_module) -> None:
    result = _capability(
        audit_module,
        [
            audit_module.Gate("independent reference", "SCIENTIFICALLY_VALIDATED", False),
            audit_module.Gate("scientific validation claim", "SCIENTIFICALLY_VALIDATED", True),
        ],
    )
    assert result["computed_level"] == "NOT_IMPLEMENTED"
    assert result["first_failed_mandatory_gate"]["gate"] == "independent reference"
    assert result["consistency_errors"]


def test_optional_vulnerability_scan_can_be_blocked_after_integration(audit_module) -> None:
    result = _capability(
        audit_module,
        [
            audit_module.Gate("implemented", "IMPLEMENTED", True),
            audit_module.Gate("identity", "IDENTITY_VERIFIED", True),
            audit_module.Gate("integration", "INTEGRATION_TEST_PASSED", True),
            audit_module.Gate(
                "vulnerability scan",
                "INTEGRATION_TEST_PASSED",
                False,
                reason="database unavailable",
                blocked=True,
                optional=True,
            ),
        ],
    )
    assert result["computed_level"] == "INTEGRATION_TEST_PASSED"
    assert result["consistency_errors"] == []
    assert result["optional_gates"][0]["gate"] == "vulnerability scan"


def test_mandatory_identity_failure_blocks_later_levels(audit_module) -> None:
    result = _capability(
        audit_module,
        [
            audit_module.Gate("implemented", "IMPLEMENTED", True),
            audit_module.Gate("identity", "IDENTITY_VERIFIED", False, reason="hash mismatch"),
            audit_module.Gate("upstream smoke", "UPSTREAM_SMOKE_PASSED", True),
        ],
    )
    assert result["computed_level"] == "IMPLEMENTED"
    assert result["first_failed_mandatory_gate"]["reason"] == "hash mismatch"
    assert result["consistency_errors"][0]["blocked_by"] == "identity"


def test_manually_supplied_contradictory_level_is_rejected(audit_module) -> None:
    result = audit_module.capability_result(
        "manual contradiction",
        [audit_module.Gate("implemented", "IMPLEMENTED", True)],
        "a" * 40,
        claimed_level="INTEGRATION_TEST_PASSED",
    )
    assert result["computed_level"] == "IMPLEMENTED"
    assert result["consistency_errors"][0]["type"] == "manual_level_exceeds_contiguous_evidence"


def test_klayout_smoke_does_not_satisfy_partial_lvs_gate(audit_module) -> None:
    tools = {"tools": [{"id": "klayout", "current_state": "IDENTITY_VERIFIED"}]}
    matrix = audit_module.capability_matrix(tools, {"container_runtime": {"docker_ps": {"return_code": 0}}})
    layer_smoke = next(
        row for row in matrix["capabilities"] if row["capability"] == "KLayout layer-population smoke"
    )
    partial_lvs = next(
        row for row in matrix["capabilities"] if row["capability"] == "KLayout partial electrical LVS"
    )
    assert layer_smoke["computed_level"] == "INTEGRATION_TEST_PASSED"
    assert partial_lvs["computed_level"] == "IMPLEMENTED"


def test_missing_evidence_hash_is_visible(audit_module) -> None:
    rows = audit_module.evidence_hashes(["missing-evidence-file.json"])
    assert rows == [{"path": "missing-evidence-file.json", "sha256": None, "exists": False}]
