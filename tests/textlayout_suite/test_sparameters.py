from __future__ import annotations

import math
from pathlib import Path

import pytest

from textlayout.simulation.sparameters import (
    compute_return_loss_db,
    estimate_z0_from_network,
    extract_s11_at_frequency,
    extract_s21_at_frequency,
    find_resonance_frequency,
)


def test_s1p_and_return_loss(tmp_path: Path) -> None:
    path = tmp_path / "reflection.s1p"
    path.write_text("# GHz S RI R 50\n5 0.2 0\n6 0.1 0\n7 0.3 0\n", encoding="utf-8")
    s11 = extract_s11_at_frequency(path, 6e9)
    assert s11 == pytest.approx(0.1 + 0j)
    assert compute_return_loss_db(s11) == pytest.approx(20.0)


def test_s2p_extracts_transmission_and_symmetric_z0(tmp_path: Path) -> None:
    path = tmp_path / "line.s2p"
    path.write_text(
        "# Hz S RI R 50\n"
        "6000000000 0 0 0.5 0 0.5 0 0 0\n",
        encoding="utf-8",
    )
    assert extract_s21_at_frequency(path, 6e9) == pytest.approx(0.5 + 0j)
    assert estimate_z0_from_network(path, 6e9) == pytest.approx(50.0)


def test_csv_fallback_and_resonance_dip(tmp_path: Path) -> None:
    path = tmp_path / "resonator.csv"
    rows = [
        "frequency_hz,s11_real,s11_imag,s21_real,s21_imag",
        "5000000000,0.1,0,0.9,0",
        "6000000000,0.8,0,0.1,0",
        "7000000000,0.1,0,0.9,0",
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert find_resonance_frequency(path) == pytest.approx(6e9)
    assert math.isclose(abs(extract_s21_at_frequency(path, 6e9)), 0.1)
