"""End-to-end: the multi-simulator IDC prompt produces every promised artifact."""

from __future__ import annotations

import json
from pathlib import Path

from textlayout import build_from_text_workflow
from textlayout.prompt import parse_prompt

_PROMPT = (
    "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap, extract "
    "capacitance if possible, then prepare JoSIM, PSCAN2, and WRspice LC "
    "resonance checks with 0.3 nH inductance"
)


def test_prompt_parses_all_three_simulator_requests() -> None:
    intent = parse_prompt(_PROMPT)
    assert intent.component == "IDC"
    assert intent.target["capacitance_pf"] == 0.6
    assert intent.target["frequency_ghz"] == 6.0
    assert intent.constraints["min_gap_um"] == 2.0
    for name in ("josim", "pscan2", "wrspice"):
        assert intent.parameters[f"{name}_check"] is True
        assert intent.parameters[f"{name}_jj_check"] is False  # LC only, no JJ words
    # The 0.3 nH is the LC-check inductor, not an IDC design target.
    assert intent.parameters["lc_inductance_nh"] == 0.3
    assert "inductance_nh" not in intent.target


def test_multi_sim_workflow_produces_all_directories_and_evidence(tmp_path: Path) -> None:
    result = build_from_text_workflow().run(_PROMPT, tmp_path / "run", execute_solver=False)
    out = tmp_path / "run"

    for filename in (
        "intent.json",
        "layout.json",
        "optimization.json",
        "output.gds",
        "output.svg",
        "verification.json",
        "simulation.json",
        "report.md",
    ):
        assert (out / filename).is_file(), filename
    assert (out / "extraction" / "capacitance_input").is_dir()
    assert (out / "extraction" / "capacitance_result.json").is_file()
    for directory in ("josim", "pscan2", "wrspice"):
        assert (out / "simulation" / directory).is_dir(), directory

    simulation = json.loads((out / "simulation" / "simulation.json").read_text(encoding="utf-8"))
    for name, label in (
        ("josim", "JOSIM_INPUT_PREPARED"),
        ("pscan2", "PSCAN2_INPUT_PREPARED"),
        ("wrspice", "WRSPICE_INPUT_PREPARED"),
    ):
        record = simulation["backends"][name]
        assert record is not None, name
        assert record["evidence_level"] == label
        assert record["solver_executed"] is False
        # Same layout-derived capacitance and the prompt's 0.3 nH everywhere.
        manifest = json.loads(
            (out / "simulation" / name / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["stray_inductance_nh"] == 0.3
        assert manifest["solver_executed"] is False
        assert manifest["parametric_gain_claimed"] is False
    # Prepared inputs can never make the benchmark physics-verified.
    assert simulation["physics_verified"] is False

    report = (out / "report.md").read_text(encoding="utf-8")
    assert "## JoSIM status" in report
    assert "Gain is not checked" in report

    assert result.circuit_simulations.keys() == {"josim", "pscan2", "wrspice"}
    summary = result.to_dict()
    assert set(summary["circuit_simulators"]) == {"josim", "pscan2", "wrspice"}
