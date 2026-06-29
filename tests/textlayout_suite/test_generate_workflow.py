"""End-to-end workflow tests: DSL → geometry → verification → export."""

from __future__ import annotations

import json

import pytest

from textlayout import build_default_workflow
from textlayout.errors import UnknownExporterError
from textlayout.schemas.dsl import LayoutSpec


def test_generate_happy_path() -> None:
    workflow = build_default_workflow()
    spec = LayoutSpec(
        component="CPW",
        parameters={"center_width_um": 10, "gap_um": 6, "length_um": 1000},
    )
    result = workflow.run(spec, formats=("json", "svg"))

    assert result.report.passed
    assert result.summary["polygon_count"] == 3
    assert set(result.artifacts) == {"json", "svg"}
    json.loads(result.artifacts["json"])  # valid JSON


def test_generate_reports_spacing_violation_without_raising() -> None:
    workflow = build_default_workflow()
    spec = LayoutSpec(
        component="CPW",
        parameters={"center_width_um": 10, "gap_um": 1.0, "length_um": 1000},
    )
    result = workflow.run(spec, formats=("json",))
    assert result.report.status == "fail"
    assert any(c.name == "minimum_gap" and c.status.value == "fail" for c in result.report.checks)


def test_generate_unknown_format_raises() -> None:
    workflow = build_default_workflow()
    spec = LayoutSpec(component="CPW", parameters={"center_width_um": 10, "gap_um": 6, "length_um": 100})
    with pytest.raises(UnknownExporterError):
        workflow.run(spec, formats=("dxf",))


def test_outputs_dict_drives_default_formats() -> None:
    workflow = build_default_workflow()
    spec = LayoutSpec(
        component="CPW",
        parameters={"center_width_um": 10, "gap_um": 6, "length_um": 100},
        outputs={"json": True, "svg": False, "gds": False},
    )
    result = workflow.run(spec)  # no explicit formats -> use spec.outputs
    assert set(result.artifacts) == {"json"}
