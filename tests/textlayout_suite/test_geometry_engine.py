"""Geometry engine tests: resolution, validation, and error mapping."""

from __future__ import annotations

import pytest

from textlayout.errors import (
    InvalidParametersError,
    UnknownComponentError,
    UnknownTechnologyError,
)
from textlayout.generators import default_registry
from textlayout.geometry import GeometryEngine
from textlayout.knowledge import default_technology_library
from textlayout.schemas.dsl import LayoutSpec


@pytest.fixture
def engine() -> GeometryEngine:
    return GeometryEngine(default_registry(discover=False), default_technology_library())


def test_engine_builds_known_component(engine: GeometryEngine) -> None:
    spec = LayoutSpec(
        component="CPW",
        parameters={"center_width_um": 10, "gap_um": 6, "length_um": 200},
    )
    result = engine.build(spec)
    assert result.geometry.name == "CPW"
    assert result.technology.name == "generic_2metal"
    assert result.params.center_width_um == 10  # type: ignore[attr-defined]


def test_engine_unknown_component(engine: GeometryEngine) -> None:
    with pytest.raises(UnknownComponentError):
        engine.build(LayoutSpec(component="DoesNotExist"))


def test_engine_unknown_technology(engine: GeometryEngine) -> None:
    spec = LayoutSpec(
        component="CPW",
        technology="nonexistent_pdk",
        parameters={"center_width_um": 10, "gap_um": 6, "length_um": 200},
    )
    with pytest.raises(UnknownTechnologyError):
        engine.build(spec)


def test_engine_invalid_parameters(engine: GeometryEngine) -> None:
    spec = LayoutSpec(
        component="CPW", parameters={"center_width_um": -10, "gap_um": 6, "length_um": 200}
    )
    with pytest.raises(InvalidParametersError) as exc:
        engine.build(spec)
    assert "center_width_um" in str(exc.value)
