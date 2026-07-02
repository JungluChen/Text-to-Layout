"""Acceptance tests for the minimal JPA design-to-simulation workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from textlayout import build_from_text_workflow
from textlayout.prompt import parse_prompt


JPA_PROMPT = (
    "Design a lumped-element JPA for 2.3 GHz with 50 MHz bandwidth, 13 dB gain "
    "target, using an IDC capacitor and SQUID-equivalent inductance. Generate layout, "
    "verify it, extract capacitance if possible, and prepare JoSIM, PSCAN2, and "
    "WRspICE simulations."
)


def test_jpa_prompt_parser_captures_physics_and_backends() -> None:
    intent = parse_prompt(JPA_PROMPT)
    assert intent.component == "JPA"
    assert intent.target == {
        "frequency_ghz": 2.3,
        "bandwidth_mhz": 50.0,
        "gain_db": 13.0,
    }
    assert intent.topology == "lumped_element_jpa"
    assert intent.capacitor_type == "IDC"
    assert intent.inductance_assumption == {
        "type": "SQUID-equivalent",
        "value_nh": 3.0,
        "source": "workflow_default",
        "user_provided": False,
    }
    assert intent.simulator_requests == ["JOSIM", "PSCAN2", "WRspice"]
    assert intent.evidence_status == ["INTENT_PARSED"]


def test_jpa_workflow_writes_complete_honest_packet(tmp_path: Path) -> None:
    out = tmp_path / "jpa_demo"
    result = build_from_text_workflow().run(JPA_PROMPT, out, execute_solver=False)
    assert result.ok

    required = (
        "intent.json",
        "design_equations.json",
        "layout.json",
        "output.gds",
        "output.svg",
        "verification.json",
        "optimization.json",
        "report.md",
        "extraction/capacitance_result.json",
        "simulation/simulation.json",
    )
    for relative in required:
        path = out / relative
        assert path.is_file() and path.stat().st_size > 0, relative

    equations = json.loads((out / "design_equations.json").read_text(encoding="utf-8"))
    assert equations["results"]["loaded_q"] == pytest.approx(46.0)
    assert equations["results"]["required_capacitance_pf"] == pytest.approx(1.5961119)
    assert equations["assumptions"]["selected_inductance_nh"] == 3.0
    assert equations["warnings"]

    layout = json.loads((out / "layout.json").read_text(encoding="utf-8"))
    assert layout["component"] == "IDC"
    assert layout["metadata"]["design_component"] == "JPA"
    assert layout["parameters"]["squid_placeholder_enabled"] is True

    verification = json.loads((out / "verification.json").read_text(encoding="utf-8"))
    assert verification["status"] == "pass"
    check_names = {check["name"] for check in verification["checks"]}
    assert {
        "minimum_width",
        "minimum_gap",
        "layer_exists",
        "bounding_box",
        "ports_exist",
        "idc_two_net_connectivity",
        "idc_no_comb_shorts",
    } <= check_names

    extraction = json.loads(
        (out / "extraction" / "capacitance_result.json").read_text(encoding="utf-8")
    )
    assert extraction["status"] == "EXTRACTION_INPUT_PREPARED"
    assert extraction["extracted_quantities"] == {}

    simulation = json.loads((out / "simulation" / "simulation.json").read_text(encoding="utf-8"))
    assert simulation["status"] == "NOT_VERIFIED"
    assert simulation["capacitance_source"] == "analytical_estimate_not_geometry_extracted"
    assert simulation["inductance_source"] == "workflow_default"
    assert simulation["analytical_f0_ghz"] == 2.3
    assert simulation["physics_verified"] is False
    for backend, label in {
        "josim": "JOSIM_INPUT_PREPARED",
        "pscan2": "PSCAN2_INPUT_PREPARED",
        "wrspice": "WRSPICE_INPUT_PREPARED",
    }.items():
        assert simulation["backends"][backend]["evidence_level"] == label
        assert simulation["backends"][backend]["solver_executed"] is False

    josim = (out / "simulation" / "josim" / "circuit.cir").read_text(encoding="ascii")
    assert ".tran" in josim
    assert "farad" not in josim.lower() and "henry" not in josim.lower()
    assert (out / "simulation" / "pscan2" / "runner.py").is_file()
    wrspice = (out / "simulation" / "wrspice" / "lc_check.cir").read_text(encoding="ascii")
    assert ".control" in wrspice and ".tran" in wrspice

    report = (out / "report.md").read_text(encoding="utf-8")
    for section in (
        "User requirement",
        "Parsed intent",
        "First-principles sizing",
        "Generated layout",
        "Verification results",
        "Extraction status",
        "JoSIM status",
        "PSCAN2 status",
        "WRspice status",
        "What is verified",
        "What is only prepared",
        "Not yet supported",
    ):
        assert section in report
    assert "PHYSICS_VERIFIED" not in report


def test_jpa_missing_capacitance_solver_is_nonfatal(tmp_path: Path) -> None:
    out = tmp_path / "missing_solver"
    result = build_from_text_workflow().run(
        JPA_PROMPT,
        out,
        execute_solver=True,
        solver_executable=str(tmp_path / "definitely-missing-fastercap"),
    )
    assert result.ok
    extraction = json.loads(
        (out / "extraction" / "capacitance_result.json").read_text(encoding="utf-8")
    )
    assert extraction["status"] == "SKIPPED_SOLVER_ABSENT"
    assert extraction["extracted_quantities"] == {}
    assert (out / "extraction" / "capacitance_input" / "idc.lst").is_file()
