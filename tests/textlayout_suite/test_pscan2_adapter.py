"""PSCAN2 adapter: input generation, honest absence, mocked execution."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

from textlayout.simulation.pscan2 import (
    PSCAN2_INPUT_PREPARED,
    PSCAN2_RESONANCE_CHECKED,
    SKIPPED_PSCAN2_ABSENT,
    PSCAN2Adapter,
    prepare_idc_pscan2,
    run_idc_pscan2,
)


def _fake_interpreter(tmp_path: Path, name: str, code: str) -> str:
    """A stand-in for `python runner.py` that runs `code` with the runner arg."""
    if sys.platform == "win32":
        fake = tmp_path / f"{name}.bat"
        fake.write_text(f'@echo off\n"{sys.executable}" -c "{code}"\n', encoding="ascii")
    else:
        fake = tmp_path / name
        fake.write_text(f'#!/bin/sh\n"{sys.executable}" -c "{code}"\n', encoding="ascii")
        os.chmod(fake, 0o755)
    return str(fake)


def test_pscan2_input_generation_is_not_spice(tmp_path: Path) -> None:
    prepared = prepare_idc_pscan2(
        tmp_path,
        capacitance_pf=0.6,
        capacitance_source="analytical estimate",
        stray_inductance_nh=0.3,
        include_jj=True,
    )
    assert prepared.status == "input_files_prepared"
    assert prepared.evidence_level == PSCAN2_INPUT_PREPARED
    for key in ("input", "hdl", "units", "runner", "manifest", "jj_input"):
        assert Path(prepared.artifacts[key]).is_file(), key
    netlist = Path(prepared.artifacts["input"]).read_text(encoding="ascii")
    # PSCAN2 dialect: '#' comments, single-letter parameter references, no
    # SPICE .tran/.print control cards inside the netlist.
    assert netlist.startswith("#")
    assert "I1 0 N001 I" in netlist
    assert ".tran" not in netlist and ".print" not in netlist
    hdl = Path(prepared.artifacts["hdl"]).read_text(encoding="ascii")
    assert "PARAMETER" in hdl and "CIRCUIT lc_check()" in hdl
    jj = Path(prepared.artifacts["jj_input"]).read_text(encoding="ascii")
    assert "rsj(IC1, RN1, CJ1)" in jj
    expected = prepared.extracted_quantities["analytical_resonance_ghz"]
    assert expected == 1.0 / (2.0 * math.pi * math.sqrt(0.3e-9 * 0.6e-12)) / 1e9


def test_missing_pscan2_reports_absent_and_keeps_inputs(tmp_path: Path) -> None:
    prepared = prepare_idc_pscan2(
        tmp_path, capacitance_pf=0.6, capacitance_source="analytical", stray_inductance_nh=0.3
    )
    result = run_idc_pscan2(prepared, executable=str(tmp_path / "missing-pscan2"))
    assert result.status == "skipped"
    assert result.evidence_level == SKIPPED_PSCAN2_ABSENT
    assert Path(result.artifacts["input"]).is_file()
    assert Path(result.artifacts["runner"]).is_file()


def test_generated_runner_refuses_to_fake_execution(tmp_path: Path) -> None:
    """Running the real runner without pscan2 must not claim execution."""
    prepared = prepare_idc_pscan2(
        tmp_path, capacitance_pf=0.6, capacitance_source="analytical", stray_inductance_nh=0.3
    )
    # sys.executable can run runner.py, but the pscan2 module is not installed
    # in the test venv, so the runner must exit with the "absent" code.
    result = run_idc_pscan2(prepared, executable=sys.executable)
    assert result.status == "skipped"
    assert result.evidence_level == SKIPPED_PSCAN2_ABSENT
    assert result.return_code is not None


def test_pscan2_execution_not_wired_stays_input_prepared(tmp_path: Path) -> None:
    prepared = prepare_idc_pscan2(
        tmp_path, capacitance_pf=0.6, capacitance_source="analytical", stray_inductance_nh=0.3
    )
    fake = _fake_interpreter(tmp_path, "fake_pscan2_present", "import sys;sys.exit(3)")
    result = run_idc_pscan2(prepared, executable=fake)
    assert result.status == "input_files_prepared"
    assert result.evidence_level == PSCAN2_INPUT_PREPARED
    assert result.solver_executed is False


def test_mocked_pscan2_execution_parses_and_checks_resonance(tmp_path: Path) -> None:
    prepared = prepare_idc_pscan2(
        tmp_path,
        capacitance_pf=0.6,
        capacitance_source="analytical",
        target_frequency_ghz=0.1,
    )
    code = (
        "import csv,math;f=open('waveform.csv','w',newline='');w=csv.writer(f);"
        "w.writerow(['time','V(N001)']);"
        "[w.writerow([i*1e-10,math.sin(2*math.pi*1e8*i*1e-10)]) for i in range(1000)];f.close()"
    )
    fake = _fake_interpreter(tmp_path, "fake_pscan2", code)
    result = run_idc_pscan2(prepared, executable=fake, resonance_tolerance_percent=5.0)
    assert result.status == "executed"
    assert result.evidence_level == PSCAN2_RESONANCE_CHECKED
    assert result.return_code == 0
    assert result.target_comparison is not None
    assert result.target_comparison["within_tolerance"] is True
    assert result.extracted_quantities["sample_count"] == 1000


def test_pscan2_adapter_env_var_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = PSCAN2Adapter()
    monkeypatch.delenv("TEXTLAYOUT_PSCAN2", raising=False)
    fake = tmp_path / "pscan2-runner.exe"
    fake.write_text("stub", encoding="ascii")
    monkeypatch.setenv("TEXTLAYOUT_PSCAN2", str(fake))
    assert adapter.discover() == str(fake)
    assert adapter.available() is True
