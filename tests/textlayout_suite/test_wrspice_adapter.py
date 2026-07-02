"""WRspice adapter: deck syntax, honest absence, rawfile parsing, mocked run."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

from textlayout.simulation.wrspice import (
    SKIPPED_WRSPICE_ABSENT,
    WRSPICE_RESONANCE_CHECKED,
    WRSPICE_INPUT_PREPARED,
    WRspiceAdapter,
    parse_wrspice_output,
    prepare_idc_wrspice,
    run_idc_wrspice,
)


def _ascii_rawfile(frequency_hz: float, points: int, dt_s: float) -> str:
    lines = [
        "Title: textlayout mocked WRspice run",
        "Date: today",
        "Plotname: Transient Analysis",
        "Flags: real",
        "No. Variables: 2",
        f"No. Points: {points}",
        "Variables:",
        "\t0\ttime\ttime",
        "\t1\tv(out)\tvoltage",
        "Values:",
    ]
    for i in range(points):
        t = i * dt_s
        lines.append(f"{i}\t{t:.12e}")
        lines.append(f"\t{math.sin(2.0 * math.pi * frequency_hz * t):.12e}")
    return "\n".join(lines) + "\n"


def test_wrspice_deck_generation_and_jj_syntax(tmp_path: Path) -> None:
    prepared = prepare_idc_wrspice(
        tmp_path,
        capacitance_pf=0.6,
        capacitance_source="analytical estimate",
        stray_inductance_nh=0.3,
        include_jj=True,
    )
    assert prepared.status == "input_files_prepared"
    assert prepared.evidence_level == WRSPICE_INPUT_PREPARED
    deck = Path(prepared.artifacts["input"]).read_text(encoding="ascii")
    # WRspice-dialect essentials: .control block with run + ascii write.
    assert ".control" in deck and ".endc" in deck and "run" in deck
    assert "set filetype=ascii" in deck
    assert "write lc_result.raw v(out)" in deck
    assert "0.6e-12" in deck and "0.3e-9" in deck
    # Plain exponent notation only — no SPICE unit-suffix ambiguity.
    assert not any(token in deck.lower() for token in ("pf", "nh", "uh", "meg"))
    jj = Path(prepared.artifacts["jj_input"]).read_text(encoding="ascii")
    # JJ element/model syntax as confirmed from the published SNAIL-TWPA deck.
    assert ".model JMODEL jj(level=1) icrit=" in jj
    assert "BJ1 JNODE 0 JMODEL" in jj


def test_missing_wrspice_reports_absent_and_keeps_deck(tmp_path: Path) -> None:
    prepared = prepare_idc_wrspice(
        tmp_path, capacitance_pf=0.6, capacitance_source="analytical", stray_inductance_nh=0.3
    )
    result = run_idc_wrspice(prepared, executable=str(tmp_path / "missing-wrspice"))
    assert result.status == "skipped"
    assert result.evidence_level == SKIPPED_WRSPICE_ABSENT
    assert Path(result.artifacts["input"]).is_file()


def test_wrspice_ascii_rawfile_parser(tmp_path: Path) -> None:
    raw = tmp_path / "lc_result.raw"
    raw.write_text(_ascii_rawfile(1.0e8, 200, 1e-10), encoding="ascii")
    parsed = parse_wrspice_output(raw)
    assert list(parsed["signals"]) == ["v(out)"]
    assert len(parsed["time_s"]) == 200
    assert parsed["time_s"][1] == pytest.approx(1e-10)
    bad = tmp_path / "bad.raw"
    bad.write_text("Variables:\nValues:\n", encoding="ascii")
    with pytest.raises(ValueError):
        parse_wrspice_output(bad)


def test_mocked_wrspice_execution_checks_resonance(tmp_path: Path) -> None:
    prepared = prepare_idc_wrspice(
        tmp_path,
        capacitance_pf=0.6,
        capacitance_source="analytical",
        target_frequency_ghz=0.1,
    )
    # No '%' characters in this inline code: cmd.exe would rewrite them
    # inside a .bat file, so the mocked rawfile is built with f-strings.
    code = (
        "import math;lines=['Title: t','Plotname: Transient Analysis','Flags: real',"
        "'No. Variables: 2','No. Points: 1000','Variables:','\\t0\\ttime\\ttime',"
        "'\\t1\\tv(out)\\tvoltage','Values:'];"
        "[lines.extend([f'{i}\\t{i*1e-10:.12e}',"
        "f'\\t{math.sin(2*math.pi*1e8*i*1e-10):.12e}']) for i in range(1000)];"
        "open('lc_result.raw','w').write('\\n'.join(lines))"
    )
    if sys.platform == "win32":
        fake = tmp_path / "fake_wrspice.bat"
        fake.write_text(f'@echo off\n"{sys.executable}" -c "{code}"\n', encoding="ascii")
    else:
        fake = tmp_path / "fake_wrspice"
        fake.write_text(f'#!/bin/sh\n"{sys.executable}" -c "{code}"\n', encoding="ascii")
        os.chmod(fake, 0o755)
    result = run_idc_wrspice(prepared, executable=str(fake), resonance_tolerance_percent=5.0)
    assert result.status == "executed"
    assert result.evidence_level == WRSPICE_RESONANCE_CHECKED
    assert result.return_code == 0
    assert result.target_comparison is not None
    assert result.target_comparison["within_tolerance"] is True


def test_wrspice_adapter_env_var_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = WRspiceAdapter()
    fake = tmp_path / "wrspice64.exe"
    fake.write_text("stub", encoding="ascii")
    monkeypatch.setenv("TEXTLAYOUT_WRSPICE", str(fake))
    assert adapter.discover() == str(fake)
    assert adapter.available() is True
