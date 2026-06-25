from __future__ import annotations

import tomllib
from pathlib import Path

from text_to_gds.signoff import evaluate_signoff, validate_value_record


def test_source_llm_physical_value_must_fail(tmp_path: Path) -> None:
    source_file = tmp_path / "extraction.json"
    source_file.write_text("{}", encoding="utf-8")
    check = validate_value_record(
        {
            "value": 6.0,
            "unit": "GHz",
            "source": "LLM",
            "method": "guess",
            "confidence": 0.5,
            "file_path": str(source_file),
        }
    )
    assert check["passed"] is False
    assert any("LLM" in issue for issue in check["issues"])


def test_skipped_solver_cannot_pass_physics_signoff(tmp_path: Path) -> None:
    gds = tmp_path / "device.gds"
    sidecar = tmp_path / "device.sidecar.json"
    extraction = tmp_path / "device.extraction.json"
    for path in (gds, sidecar, extraction):
        path.write_text("{}", encoding="utf-8")

    result = evaluate_signoff(
        {
            "claim": "physics signoff",
            "gds_path": str(gds),
            "sidecar_path": str(sidecar),
            "drc": {"status": "passed"},
            "extraction": {"result_path": str(extraction)},
            "analytical_sanity": {"passed": True},
            "values": [
                {
                    "value": 50.0,
                    "unit": "ohm",
                    "source": "extraction",
                    "method": "cpw_geometry",
                    "confidence": 0.8,
                    "file_path": str(extraction),
                }
            ],
            "solvers": [{"solver": "openEMS", "status": "skipped", "reason": "not installed"}],
            "count_skipped_solver_as_evidence": True,
        }
    )
    assert result["level"] == 3
    assert result["passed"] is False
    assert any("skipped solver" in blocker for blocker in result["blockers"])
    assert any("Level 5" in blocker for blocker in result["blockers"])


def test_missing_solver_output_file_cannot_be_called_executed(tmp_path: Path) -> None:
    gds = tmp_path / "device.gds"
    sidecar = tmp_path / "device.sidecar.json"
    extraction = tmp_path / "device.extraction.json"
    for path in (gds, sidecar, extraction):
        path.write_text("{}", encoding="utf-8")

    result = evaluate_signoff(
        {
            "gds_path": str(gds),
            "sidecar_path": str(sidecar),
            "drc": {"status": "passed"},
            "extraction": {"result_path": str(extraction)},
            "analytical_sanity": {"passed": True},
            "values": [
                {
                    "value": 6.0,
                    "unit": "GHz",
                    "source": "extraction",
                    "method": "geometry",
                    "confidence": 0.8,
                    "file_path": str(extraction),
                }
            ],
            "solvers": [
                {
                    "solver": "openEMS",
                    "status": "executed",
                    "output_file": str(tmp_path / "missing.s2p"),
                }
            ],
        }
    )
    assert result["level"] == 3
    assert result["passed"] is False
    assert any("without output file" in blocker for blocker in result["blockers"])


def test_gds_with_no_sidecar_cannot_pass_extraction(tmp_path: Path) -> None:
    gds = tmp_path / "device.gds"
    gds.write_text("{}", encoding="utf-8")
    result = evaluate_signoff({"gds_path": str(gds), "drc": {"status": "passed"}})
    assert result["level"] == 1
    assert result["passed"] is False
    assert any("no sidecar" in blocker for blocker in result["blockers"])


def test_benchmark_layout_and_panel_assets_are_separate() -> None:
    root = Path(__file__).resolve().parents[1]
    for index in range(1, 7):
        layout = next((root / "assets").glob(f"benchmark_{index:02d}_*_layout.png"), None)
        panel = next((root / "assets").glob(f"benchmark_{index:02d}_*_benchmark.png"), None)
        assert layout is not None, f"missing layout asset {index}"
        assert panel is not None, f"missing benchmark panel asset {index}"
        assert layout.name != panel.name


def test_skill_install_paths_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in [
        "text-to-gds",
        "text-to-gds-simulation",
        "text-to-gds-circuit-design",
        "text-to-gds-layout-design",
        "text-to-gds-signoff",
        "text-to-gds-physics-signoff",
    ]:
        assert (root / "skills" / name / "SKILL.md").is_file()


def test_workflow_console_commands_are_exposed() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project["project"]["scripts"]
    for command in [
        "text-to-gds",
        "text-to-gds-simulation",
        "text-to-gds-circuit-design",
        "text-to-gds-layout-design",
        "text-to-gds-signoff",
        "text-to-gds-physics-signoff",
    ]:
        assert command in scripts
