from __future__ import annotations

import pytest

from text_to_gds.physics.extraction_provenance import ExtractedQuantity, ProvenanceChain


def test_extracted_quantity_creation():
    q = ExtractedQuantity(
        value=1.23,
        unit="GHz",
        source="simulation",
        method="eigenmode",
        validity_range=(0.8, 2.0),
        confidence=0.95,
        dependencies=[],
        note="resonator frequency",
    )
    assert q.value == 1.23
    assert q.unit == "GHz"
    assert q.source == "simulation"
    assert q.method == "eigenmode"
    assert q.validity_range == (0.8, 2.0)
    assert q.confidence == pytest.approx(0.95)
    assert q.dependencies == []
    assert q.note == "resonator frequency"


def test_provenance_chain():
    freq = ExtractedQuantity(
        value=1.23,
        unit="GHz",
        source="simulation",
        method="eigenmode",
        validity_range=(0.8, 2.0),
        confidence=0.95,
        dependencies=[],
        note="resonator frequency",
    )
    q = ExtractedQuantity(
        value=50.0,
        unit="fF",
        source="fitting",
        method="circle_fit",
        validity_range=(10.0, 100.0),
        confidence=0.88,
        dependencies=["freq"],
        note="coupling capacitance",
    )
    chain = ProvenanceChain()
    chain.add("freq", freq)
    chain.add("coupling_cap", q)
    assert chain.get("coupling_cap") is q
    assert chain.get("freq") is freq
    assert chain.resolve("coupling_cap") == [q, freq]


def test_provenance_chain_rejects_source_mix():
    est = ExtractedQuantity(
        value=10.0,
        unit="nH",
        source="estimated",
        method="analytical",
        validity_range=(5.0, 20.0),
        confidence=0.70,
        dependencies=[],
        note="kinetic inductance",
    )
    sim = ExtractedQuantity(
        value=1.0,
        unit="GHz",
        source="simulation",
        method="em_sim",
        validity_range=(0.5, 2.0),
        confidence=0.95,
        dependencies=[],
        note="frequency",
    )
    chain = ProvenanceChain()
    chain.add("lk", est)
    chain.add("freq", sim)
    with pytest.raises(ValueError, match="mix"):
        chain.resolve("lk")
