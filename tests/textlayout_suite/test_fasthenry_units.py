"""Check conductivity units independently using Ohm's law and the real solver."""

import re

import pytest

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import prepare_spiral_fasthenry, run_fasthenry
from textlayout.simulation.runners import find_executable


def prepared_spiral(tmp_path):
    spec = LayoutSpec(component="SpiralInductor", parameters={
        "turns": 4, "outer_dimension_um": 100, "trace_width_um": 4,
        "spacing_um": 2, "thickness_um": 0.2})
    workflow = build_default_workflow()
    result = workflow.run(spec, formats=())
    prepared = prepare_spiral_fasthenry(spec, result.geometry,
                                      workflow.technology(spec.technology), tmp_path)
    return prepared, result.geometry


def test_normal_metal_conductivity_is_converted_to_micrometre_units(tmp_path):
    from pathlib import Path

    prepared, _ = prepared_spiral(tmp_path)
    text = Path(prepared.artifacts["input"]).read_text()
    sigma = float(re.search(r"sigma=([\deE.+-]+)", text).group(1))
    assert ".units um" in text
    # FastHenry divides input conductivity by the length-unit scale.
    assert sigma / 1e-6 == pytest.approx(5.8e7)


def test_real_fasthenry_resistance_matches_ohms_law(tmp_path):
    from pathlib import Path

    executable = find_executable(("fasthenry",), env_var="TEXTLAYOUT_FASTHENRY")
    if executable is None:
        pytest.skip("Real FastHenry is optional")
    prepared, geometry = prepared_spiral(tmp_path)
    result = run_fasthenry(prepared, executable=executable)
    assert result.status == "executed"
    text = Path(result.artifacts["zc_matrix"]).read_text()
    row = text.split("Impedance matrix for frequency = 1e+06 1 x 1\n", 1)[1].splitlines()[0]
    resistance = float(row.split()[0])
    length_m = geometry.metadata["centerline_length_um"] * 1e-6
    expected = length_m / (5.8e7 * 4e-6 * 0.2e-6)
    assert resistance == pytest.approx(expected, rel=1e-4)
