"""scripts/check_project_claims.py and scripts/generate_project_status.py.

Imports the scripts as modules (they are argparse scripts, not a package) so
each check function can be unit-tested against synthetic fixture repos
without touching the real README/pyproject.toml.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def claims_module():
    return _load("check_project_claims", SCRIPTS_DIR / "check_project_claims.py")


@pytest.fixture()
def status_module():
    return _load("generate_project_status", SCRIPTS_DIR / "generate_project_status.py")


class TestNegationDetection:
    def test_negated_claims_are_not_flagged(self, claims_module) -> None:
        assert claims_module._NEGATION_RE.search("No example is fabrication-ready.")
        assert claims_module._NEGATION_RE.search("fabrication ready **no**.")
        assert claims_module._NEGATION_RE.search(
            "Nothing in this repository is FABRICATION READY"
        )
        assert claims_module._NEGATION_RE.search("No benchmark is FABRICATION READY.")

    def test_unnegated_claim_is_detected(self, claims_module) -> None:
        assert not claims_module._NEGATION_RE.search(
            "This chip is fabrication-ready today."
        )

    def test_legend_row_is_recognized(self, claims_module) -> None:
        assert claims_module.legend_row_re.match(
            "| **FABRICATION READY**         | Process-specific DRC complete |"
        )
        assert not claims_module.legend_row_re.match(
            "Nothing in this repository is FABRICATION READY today."
        )


class TestPhysicsVerifiedCrossCheck:
    def test_readme_and_index_agreement_passes(self, tmp_path, monkeypatch, claims_module) -> None:
        showcase = tmp_path / "examples" / "showcase"
        showcase.mkdir(parents=True)
        (showcase / "index.json").write_text(
            json.dumps(
                {
                    "examples": [
                        {
                            "id": "01_idc",
                            "evidence_status": "NUMERICALLY_CONVERGED",
                            "simulation_status": "NUMERICALLY_CONVERGED",
                            "solver_executed": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "| 1 | IDC | prompt | examples/showcase/01_idc/output.png | "
            "**NUMERICALLY_CONVERGED** executed |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_physics_verified_and_execution_claims(errors)
        assert errors == []

    def test_readme_overclaims_physics_verified_is_caught(
        self, tmp_path, monkeypatch, claims_module
    ) -> None:
        showcase = tmp_path / "examples" / "showcase"
        showcase.mkdir(parents=True)
        (showcase / "index.json").write_text(
            json.dumps(
                {
                    "examples": [
                        {
                            "id": "02_cpw",
                            "evidence_status": "SKIPPED_SOLVER_ABSENT",
                            "simulation_status": "SKIPPED_SOLVER_ABSENT",
                            "solver_executed": False,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "| 2 | CPW | prompt | examples/showcase/02_cpw/output.png | "
            "**PHYSICS_VERIFIED** |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_physics_verified_and_execution_claims(errors)
        # A README row claiming PHYSICS_VERIFIED against a SKIPPED_SOLVER_ABSENT
        # index entry legitimately trips two independent checks: the status
        # mismatch itself, and the implied-execution claim it carries.
        assert len(errors) == 2
        assert all("02_cpw" in e for e in errors)
        assert any("PHYSICS_VERIFIED" in e for e in errors)
        assert any("solver execution" in e for e in errors)

    def test_index_verified_but_readme_silent_is_caught(
        self, tmp_path, monkeypatch, claims_module
    ) -> None:
        showcase = tmp_path / "examples" / "showcase"
        showcase.mkdir(parents=True)
        (showcase / "index.json").write_text(
            json.dumps(
                {
                    "examples": [
                        {
                            "id": "03_spiral",
                            "evidence_status": "NUMERICALLY_CONVERGED",
                            "simulation_status": "NUMERICALLY_CONVERGED",
                            "solver_executed": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "| 3 | Spiral | prompt | examples/showcase/03_spiral/output.png | "
            "ANALYTICAL_ONLY |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_physics_verified_and_execution_claims(errors)
        assert len(errors) == 1
        assert "03_spiral" in errors[0]

    def test_readme_implies_execution_without_solver_run_is_caught(
        self, tmp_path, monkeypatch, claims_module
    ) -> None:
        showcase = tmp_path / "examples" / "showcase"
        showcase.mkdir(parents=True)
        (showcase / "index.json").write_text(
            json.dumps(
                {
                    "examples": [
                        {
                            "id": "04_res",
                            "evidence_status": "SKIPPED_SOLVER_ABSENT",
                            "simulation_status": "SKIPPED_SOLVER_ABSENT",
                            "solver_executed": False,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "| 4 | Resonator | prompt | examples/showcase/04_res/output.png | "
            "openEMS executed successfully |\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_physics_verified_and_execution_claims(errors)
        assert len(errors) == 1
        assert "04_res" in errors[0]


class TestVersionConsistency:
    def test_matching_versions_pass(self, tmp_path, monkeypatch, claims_module) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8"
        )
        (tmp_path / "IMPLEMENTATION_REPORT.md").write_text(
            "**Version:** 1.2.3\n", encoding="utf-8"
        )
        (tmp_path / "CHANGELOG.md").write_text("## [1.2.3] - today\n", encoding="utf-8")
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_version_consistency(errors)
        assert errors == []

    def test_mismatched_implementation_report_version_is_caught(
        self, tmp_path, monkeypatch, claims_module
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8"
        )
        (tmp_path / "IMPLEMENTATION_REPORT.md").write_text(
            "**Version:** 9.9.9\n", encoding="utf-8"
        )
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_version_consistency(errors)
        assert len(errors) == 1
        assert "9.9.9" in errors[0]

    def test_mismatched_changelog_version_is_caught(
        self, tmp_path, monkeypatch, claims_module
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8"
        )
        (tmp_path / "CHANGELOG.md").write_text("## [4.5.6] - today\n", encoding="utf-8")
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_version_consistency(errors)
        assert len(errors) == 1
        assert "4.5.6" in errors[0]


class TestFullCheckAgainstRealRepo:
    def test_current_repo_passes_all_checks(self) -> None:
        """Regression guard: the real repo must stay claim-consistent."""
        module = _load("check_project_claims_live", SCRIPTS_DIR / "check_project_claims.py")
        errors = module.run_all_checks()
        assert errors == [], f"Repo has claim inconsistencies: {errors}"


class TestIndexMatchesSimulationJson:
    """Regression guard for a real bug found during Sprint 5: index.json claimed
    SKIPPED_SOLVER_ABSENT for examples/showcase/02_cpw_50ohm while its own
    simulation.json showed a real, completed openEMS execution -- a summary
    file silently under-reporting the evidence it was supposed to summarize."""

    def _fixture(self, tmp_path, *, index_executed: bool, simulation_executed: bool) -> None:
        showcase = tmp_path / "examples" / "showcase"
        example_dir = showcase / "02_cpw"
        example_dir.mkdir(parents=True)
        (showcase / "index.json").write_text(
            json.dumps(
                {
                    "examples": [
                        {
                            "id": "02_cpw",
                            "artifact_dir": "examples/showcase/02_cpw",
                            "solver_executed": index_executed,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (example_dir / "simulation.json").write_text(
            json.dumps({"solver_executed": simulation_executed}), encoding="utf-8"
        )

    def test_agreement_passes(self, tmp_path, monkeypatch, claims_module) -> None:
        self._fixture(tmp_path, index_executed=True, simulation_executed=True)
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_index_matches_simulation_json(errors)
        assert errors == []

    def test_index_under_reporting_execution_is_caught(self, tmp_path, monkeypatch, claims_module) -> None:
        """The exact real-world case: index.json says skipped, simulation.json says executed."""
        self._fixture(tmp_path, index_executed=False, simulation_executed=True)
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_index_matches_simulation_json(errors)
        assert len(errors) == 1
        assert "02_cpw" in errors[0]
        assert "stale" in errors[0]

    def test_index_over_reporting_execution_is_also_caught(
        self, tmp_path, monkeypatch, claims_module
    ) -> None:
        """The opposite direction is equally a bug: over-claiming evidence."""
        self._fixture(tmp_path, index_executed=True, simulation_executed=False)
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_index_matches_simulation_json(errors)
        assert len(errors) == 1

    def test_missing_simulation_json_is_not_an_error_here(
        self, tmp_path, monkeypatch, claims_module
    ) -> None:
        """A missing simulation.json is a different problem (validate_readme_claims.py
        catches that); this check only compares fields when both files exist."""
        showcase = tmp_path / "examples" / "showcase"
        showcase.mkdir(parents=True)
        (showcase / "index.json").write_text(
            json.dumps(
                {
                    "examples": [
                        {
                            "id": "03_no_sim",
                            "artifact_dir": "examples/showcase/03_no_sim",
                            "solver_executed": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(claims_module, "ROOT", tmp_path)
        errors: list[str] = []
        claims_module.check_index_matches_simulation_json(errors)
        assert errors == []


class TestProjectStatusGenerator:
    def test_build_status_has_required_sections(self, status_module) -> None:
        status = status_module.build_status()
        assert status["schema"] == status_module.STATUS_SCHEMA
        assert "package_version" in status
        assert "showcase" in status
        assert "pdk_status" in status
        assert "known_limitations" in status

    def test_missing_test_report_is_reported_honestly_not_fabricated(
        self, tmp_path, monkeypatch, status_module
    ) -> None:
        monkeypatch.setattr(status_module, "ROOT", tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "1.0.0"\n', encoding="utf-8"
        )
        (tmp_path / "README.md").write_text("", encoding="utf-8")
        result = status_module._read_test_report()
        assert result is None

    def test_saved_test_report_is_read_back_verbatim(
        self, tmp_path, monkeypatch, status_module
    ) -> None:
        monkeypatch.setattr(status_module, "ROOT", tmp_path)
        evidence_dir = tmp_path / "out" / "evidence"
        evidence_dir.mkdir(parents=True)
        payload = {"passed": 42, "failed": 1, "skipped": 0, "source": "unit-test"}
        (evidence_dir / "test_report.json").write_text(json.dumps(payload), encoding="utf-8")
        result = status_module._read_test_report()
        assert result == payload

    def test_no_pdk_claims_foundry_validated(self, status_module) -> None:
        pdk_status = status_module._pdk_status()
        assert pdk_status["any_foundry_validated"] is False
        assert all(not pdk["foundry_validated"] for pdk in pdk_status["pdks"])

    def test_markdown_render_includes_honesty_note_when_no_test_report(
        self, status_module
    ) -> None:
        status = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "package_version": "0.0.0",
            "showcase": {
                "total_examples": 0,
                "solver_backed": [],
                "skipped_solver_absent": [],
                "analytical_only": [],
            },
            "cli_commands": {},
            "test_report": {"available": False, "note": "no report saved"},
            "known_limitations": [],
            "pdk_status": {"pdks": [], "fabrication_readiness": "NOT_FABRICATION_READY"},
            "epr_support": {
                "cli_command": True,
                "prompt_verify_flag": "--include-epr",
                "statuses": ["EPR_ANALYTICAL_ONLY"],
                "default_backend": "analytical",
                "field_solver_verified_by_default": False,
            },
            "measurement_support": {
                "compare_command": True,
                "calibrate_command": True,
                "fixtures": [],
                "fixtures_are_synthetic": True,
                "note": "synthetic",
            },
        }
        markdown = status_module.render_markdown(status)
        assert "No saved test report available" in markdown
