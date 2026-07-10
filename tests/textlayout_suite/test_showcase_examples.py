"""Committed showcase artifacts must back every claim they make.

These tests run against the *committed* ``examples/showcase`` tree — the same
artifacts the README table links to. If an example claims PHYSICS_VERIFIED
without solver-owned output on disk, this suite fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHOWCASE = ROOT / "examples" / "showcase"

REQUIRED_FILES = (
    "prompt.txt",
    "intent.json",
    "layout.json",
    "output.gds",
    "output.svg",
    "output.png",
    "verification.json",
    "klayout_readback.json",
    "simulation.json",
    "optimization.json",
    "workflow_trace.json",
    "report.md",
    "README.md",
)

EXPECTED_IDS = (
    "01_idc_0p6pf",
    "02_cpw_50ohm",
    "03_idc_cpw_test_structure",
    "04_spiral_inductor_3nh",
    "05_quarter_wave_resonator_6ghz",
    "06_research_test_chip",
)


def _reject_json_constant(token: str) -> float:
    raise AssertionError(
        f"{token!r} is not valid JSON; a solver artifact must not contain bare NaN/Infinity"
    )


def _index() -> dict:
    return json.loads((SHOWCASE / "index.json").read_text(encoding="utf-8"))


def test_index_lists_all_six_examples() -> None:
    entries = {entry["id"] for entry in _index()["examples"]}
    assert entries == set(EXPECTED_IDS)


@pytest.mark.parametrize("example_id", EXPECTED_IDS)
def test_every_example_has_full_artifact_chain(example_id: str) -> None:
    folder = SHOWCASE / example_id
    assert folder.is_dir(), f"missing artifact folder {folder}"
    for name in REQUIRED_FILES:
        path = folder / name
        assert path.is_file() and path.stat().st_size > 0, f"{example_id}: missing {name}"


@pytest.mark.parametrize("example_id", EXPECTED_IDS)
def test_no_example_claims_fabrication_ready(example_id: str) -> None:
    readme = (SHOWCASE / example_id / "README.md").read_text(encoding="utf-8")
    assert "NOT_FABRICATION_READY" in readme
    assert "FABRICATION_READY**" not in readme.replace("NOT_FABRICATION_READY", "")


@pytest.mark.parametrize("example_id", EXPECTED_IDS)
def test_physics_verified_claims_are_solver_backed(example_id: str) -> None:
    folder = SHOWCASE / example_id
    simulation = json.loads((folder / "simulation.json").read_text(encoding="utf-8"))
    evidence = (simulation.get("evidence") or [{}])[0]
    if evidence.get("status") != "PHYSICS_VERIFIED":
        return
    assert simulation["solver_executed"] is True
    comparison = simulation["target_comparison"]
    assert comparison["within_tolerance"] is True
    artifacts = simulation["artifacts"]
    for key in ("solver_stdout", "solver_stderr"):
        raw = Path(artifacts[key])
        candidates = [raw] if raw.is_absolute() else [folder / raw]
        # Artifacts may be recorded relative to the repo or the example folder.
        candidates += [ROOT / raw, folder / raw.name, folder / "extraction" / "capacitance_input" / raw.name]
        assert any(c.is_file() and c.stat().st_size > 0 for c in candidates), (
            f"{example_id}: PHYSICS_VERIFIED without solver-owned {key} on disk"
        )


@pytest.mark.parametrize("example_id", EXPECTED_IDS)
def test_skipped_examples_carry_no_extracted_value(example_id: str) -> None:
    simulation = json.loads(
        (SHOWCASE / example_id / "simulation.json").read_text(encoding="utf-8")
    )
    evidence = (simulation.get("evidence") or [{}])[0]
    if evidence.get("status") in {"SKIPPED_SOLVER_ABSENT", "SIMULATION_INPUT_PREPARED"}:
        assert evidence.get("extracted_value") is None
        assert simulation.get("solver_executed") in (False, None)


def test_fake_physics_verified_showcase_claim_fails_validation(tmp_path: Path) -> None:
    """Claim validation must reject PHYSICS_VERIFIED for an out-of-tolerance example."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_readme_claims", ROOT / "scripts" / "validate_readme_claims.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    real = (ROOT / "README.md").read_text(encoding="utf-8")
    # The resonator's generated cell now reports SIMULATION_INVALID. Forge a
    # PHYSICS_VERIFIED claim for it: canonical evidence extracted nothing, so
    # claim validation must reject the doctored README.
    marker = "**SIMULATION_INVALID** — openEMS+scikit-rf ran to completion"
    start = real.index(marker)
    end = real.index("**NOT_FABRICATION_READY**", start)
    doctored = real[:start] + "**PHYSICS_VERIFIED** — totally real, trust me. " + real[end:]
    assert doctored != real, "expected to find the quarter-wave resonator invalid-status cell"
    fake_readme = tmp_path / "README.md"
    fake_readme.write_text(doctored, encoding="utf-8")
    errors = module.validate(fake_readme, root=ROOT)
    assert any(
        "05_quarter_wave_resonator_6ghz" in error
        and ("PHYSICS_VERIFIED" in error or "solver" in error)
        for error in errors
    ), errors


def test_test_chip_has_honest_subblock_simulation_map() -> None:
    payload = json.loads(
        (SHOWCASE / "06_research_test_chip" / "tile_simulation_map.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["full_tile_solver_executed"] is False
    assert payload["full_tile_status"] == "NOT_MODELED"
    assert payload["fabrication_status"] == "NOT_FABRICATION_READY"
    assert payload["subblocks"]["IDC"]["solver_executed"] is True
    assert payload["subblocks"]["SpiralInductor"]["solver_executed"] is True
    assert payload["subblocks"]["Resonator"]["solver"] == "openEMS"
    assert payload["subblocks"]["AlignmentMarksAndLabels"]["status"] == "GEOMETRY_ONLY"


def test_spiral_optimizer_retains_candidates_and_selects_verified_geometry() -> None:
    folder = SHOWCASE / "04_spiral_inductor_3nh"
    payload = json.loads((folder / "optimization.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "textlayout.fasthenry-closed-loop-optimization.v1"
    assert payload["physics_verified"] is True
    assert payload["reason_for_stopping"] == "target tolerance reached"
    assert len(payload["candidates"]) >= 2
    selected = payload["selected_candidate"]
    assert selected["target_comparison"]["within_tolerance"] is True
    assert selected["klayout_readback_passed"] is True
    for candidate in payload["candidates"]:
        assert candidate["verification_passed"] is True
        for relative in candidate["artifacts"].values():
            assert (folder / relative).is_file()


def test_idc_cpw_region_map_does_not_promote_whole_structure() -> None:
    payload = json.loads(
        (SHOWCASE / "03_idc_cpw_test_structure" / "region_evidence_map.json").read_text(
            encoding="utf-8"
        )
    )
    regions = {region["name"]: region for region in payload["regions"]}
    assert regions["embedded_idc"]["status"] == "PHYSICS_VERIFIED"
    assert regions["cpw_launch_and_feed"]["solver"] == "openEMS"
    assert regions["transition_region"]["status"] == "NOT_MODELED"
    assert payload["whole_structure_verified"] is False


def test_root_readme_showcase_rows_link_to_committed_folders() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for example_id in EXPECTED_IDS:
        assert f"examples/showcase/{example_id}" in readme, (
            f"README must link showcase example {example_id}"
        )


class TestResonatorRunIsHonestlyInvalid:
    """showcase 05's openEMS run produced an all-NaN Touchstone.

    It once reported `resonance_frequency_ghz: 3.0` -- the first point of the
    sweep -- because an argmin over all-NaN magnitudes returns index 0 (every
    NaN comparison is False). The parser now rejects that data outright; these
    tests stop the fabricated number from creeping back into the artifact.
    """

    RESONATOR = SHOWCASE / "05_quarter_wave_resonator_6ghz"
    TOUCHSTONE = RESONATOR / "extraction" / "capacitance_input" / "openems_result.s2p"

    def _result(self) -> dict:
        # strict=True: bare NaN is not valid JSON and must not reappear
        return json.loads(
            (self.RESONATOR / "openems_result.json").read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )

    def test_touchstone_is_all_non_finite(self) -> None:
        assert self.TOUCHSTONE.is_file()
        body = self.TOUCHSTONE.read_text(encoding="utf-8")
        assert "NaN" in body, "fixture premise changed: the s2p is no longer all-NaN"

    def test_parser_refuses_to_extract_from_it(self) -> None:
        from textlayout.simulation.runners import extract_resonance_metrics_from_touchstone

        with pytest.raises(ValueError, match="non-finite"):
            extract_resonance_metrics_from_touchstone(self.TOUCHSTONE)

    def test_artifact_claims_simulation_invalid_and_extracts_nothing(self) -> None:
        result = self._result()
        assert result["status"] == "SIMULATION_INVALID"
        assert result["extracted_quantities"] == {}
        assert result["target_comparison"]["extracted"] is None
        assert result["target_comparison"]["within_tolerance"] is False

    def test_artifact_never_reports_the_sweep_edge_as_a_resonance(self) -> None:
        result = self._result()
        assert "resonance_frequency_ghz" not in result["extracted_quantities"]
        # the withdrawn claim is retained for provenance, clearly labelled, in the
        # canonical SupersededClaim shape
        superseded = result["superseded_claim"]
        assert superseded["status"] == "RESONANCE_FREQUENCY_EXTRACTED"
        assert superseded["extracted_value"] == 3.0
        assert superseded["extracted_unit"] == "GHz"
        assert "not a resonance" in superseded["why_withdrawn"]

    def test_solver_execution_is_still_reported_truthfully(self) -> None:
        """It really did run: rc 0, ~1011 s. Invalid output is not a skipped run."""
        result = self._result()
        assert result["backend_status"] == "executed"
        assert result["return_code"] == 0
        assert result["runtime_seconds"] > 0
