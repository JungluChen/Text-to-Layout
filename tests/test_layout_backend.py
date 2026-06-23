from __future__ import annotations

import pytest

from text_to_gds.layout.technology import (
    GDSFactorySelector,
    KQCircuitsSelector,
    PCellSelector,
    SuperconductingTechnology,
    TechnologyFactory,
)


def test_technology_selection():
    tech = SuperconductingTechnology(
        name="ncu_alox",
        backend="kqcircuits",
        process_id="ncu_alox_2026",
    )
    selector = tech.selector()
    assert isinstance(selector, KQCircuitsSelector)
    assert isinstance(selector, PCellSelector)
    assert selector.backend == "kqcircuits"


def test_gdsfactory_selector():
    sel = GDSFactorySelector()
    assert sel.has_pcell("straight")
    assert not sel.has_pcell("cpw_straight")
    assert "straight" in sel.supported_pcells()
    cell = sel.create_pcell("straight", {"length": 100.0})
    assert cell["backend"] == "gdsfactory"
    assert cell["params"]["length"] == 100.0


def test_kqcircuits_selector():
    sel = KQCircuitsSelector()
    assert sel.has_pcell("cpw_straight")
    assert not sel.has_pcell("straight")
    cell = sel.create_pcell("cpw_straight", {"length": 500.0})
    assert cell["backend"] == "kqcircuits"


def test_technology_factory_unknown_backend():
    with pytest.raises(ValueError, match="Unknown backend"):
        TechnologyFactory.create("nonexistent")


def test_technology_factory_creates_correct_backends():
    assert isinstance(TechnologyFactory.create("kqcircuits"), KQCircuitsSelector)
    assert isinstance(TechnologyFactory.create("gdsfactory"), GDSFactorySelector)


def test_kqcircuits_wrapper_availability():
    from text_to_gds.layout.kqcircuits_wrapper import KQCircuitsWrapper

    wrapper = KQCircuitsWrapper()
    assert isinstance(wrapper.is_available(), bool)
    assert hasattr(wrapper, "get_junction_class")
    assert hasattr(wrapper, "get_resonator_class")
    assert hasattr(wrapper, "get_transmon_class")
    assert hasattr(wrapper, "create_junction")
    assert hasattr(wrapper, "create_resonator")
    assert hasattr(wrapper, "create_transmon")
