"""DSL schema firewall tests: invalid specs are rejected before geometry runs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from textlayout.schemas.dsl import DSL_VERSION, CPWSpec, LayoutSpec


def test_layout_spec_defaults() -> None:
    spec = LayoutSpec(component="CPW", parameters={"center_width_um": 10, "gap_um": 6, "length_um": 100})
    assert spec.dsl_version == DSL_VERSION
    assert spec.technology == "generic_2metal"
    assert spec.origin == (0.0, 0.0)


def test_layout_spec_is_frozen_and_forbids_extra() -> None:
    spec = LayoutSpec(component="CPW")
    with pytest.raises(ValidationError):
        spec.component = "IDC"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        LayoutSpec(component="CPW", bogus_field=1)  # type: ignore[call-arg]


def test_cpw_spec_rejects_non_physical_values() -> None:
    with pytest.raises(ValidationError):
        CPWSpec(center_width_um=-1, gap_um=6, length_um=100)
    with pytest.raises(ValidationError):
        CPWSpec(center_width_um=10, gap_um=0, length_um=100)


def test_cpw_spec_forbids_unknown_parameter() -> None:
    with pytest.raises(ValidationError):
        CPWSpec(center_width_um=10, gap_um=6, length_um=100, typo=3)  # type: ignore[call-arg]
