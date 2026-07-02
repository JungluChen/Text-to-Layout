"""JoSIM circuit-level support for the IDC hero workflow."""

from __future__ import annotations

import math
import os
from pathlib import Path
import sys

import numpy as np
import pytest

from textlayout.simulation.josim import (
    JOSIM_RESONANCE_CHECKED,
    SKIPPED_JOSIM_ABSENT,
    estimate_resonance_ghz,
    prepare_idc_josim,
    run_idc_josim,
)


def test_josim_deck_snapshot_and_syntax_hygiene(tmp_path: Path) -> None:
    prepared = prepare_idc_josim(
        tmp_path,
        capacitance_pf=0.6,
        capacitance_source="extracted",
        target_frequency_ghz=6.0,
        include_jj=True,
    )
    deck = Path(prepared.artifacts["input"]).read_text(encoding="ascii")
    assert deck.startswith("* IDC passive LC transient sanity check")
    assert ".tran " in deck and deck.rstrip().endswith(".end")
    assert ".print V(OUT) I(L_STRAY)" in deck
    assert not any(unit in deck.lower() for unit in ("farad", "henry", "ohm", "kelvin"))
    assert not any(character in token for token in ("IN", "OUT") for character in ".|")
    jj = Path(prepared.artifacts["jj_input"]).read_text(encoding="ascii")
    assert "BJJ JJNODE 0 JMODEL" in jj
    assert ".model JMODEL jj(" in jj
    assert ".option seed=1" in jj


def test_missing_josim_keeps_prepared_deck(tmp_path: Path) -> None:
    prepared = prepare_idc_josim(tmp_path, capacitance_pf=0.6, capacitance_source="analytical")
    result = run_idc_josim(prepared, executable=str(tmp_path / "missing-josim"))
    assert result.status == "skipped"
    assert result.evidence_level == SKIPPED_JOSIM_ABSENT
    assert Path(result.artifacts["input"]).is_file()


def test_mocked_josim_records_execution_and_metrics(tmp_path: Path) -> None:
    prepared = prepare_idc_josim(
        tmp_path,
        capacitance_pf=0.6,
        capacitance_source="extracted",
        target_frequency_ghz=0.1,
    )
    code = (
        "import csv,math,sys;f=open(sys.argv[1],'w',newline='');w=csv.writer(f);"
        "w.writerow(['time','V(OUT)']);"
        "[w.writerow([i*1e-10,math.sin(2*math.pi*1e8*i*1e-10)]) for i in range(1000)];f.close()"
    )
    if sys.platform == "win32":
        fake = tmp_path / "fake_josim.bat"
        fake.write_text(f'@echo off\n"{sys.executable}" -c "{code}" %2\n', encoding="ascii")
    else:
        fake = tmp_path / "fake_josim"
        fake.write_text(f'#!/bin/sh\n"{sys.executable}" -c "{code}" "$2"\n', encoding="ascii")
        os.chmod(fake, 0o755)
    result = run_idc_josim(prepared, executable=str(fake), resonance_tolerance_percent=5.0)
    assert result.status == "executed"
    assert result.evidence_level == JOSIM_RESONANCE_CHECKED
    assert result.return_code == 0
    assert result.runtime_seconds is not None
    assert result.command and Path(result.artifacts["result"]).stat().st_size > 0
    assert result.extracted_quantities["sample_count"] == 1000


def test_lc_fft_post_processing_matches_known_resonance() -> None:
    frequency_hz = 6.0e9
    time = np.arange(0.0, 20e-9, 1e-12)
    signal = np.sin(2.0 * math.pi * frequency_hz * time)
    measured = estimate_resonance_ghz(time.tolist(), signal.tolist())
    assert measured == pytest.approx(6.0, rel=0.01)
