"""Geometry-derived topology checks for the transmon device.

These tests do NOT trust net labels — they write real GDS, then extract the
conductor graph from polygon geometry (merged metal islands, JJ overlaps) and
assert the transmon SQUID topology:

    PASS:  island_top --JJ_left--  island_bottom
           island_top --JJ_right-- island_bottom   (two JJs => one SQUID)

    FAIL:  island_top *shorted to* island_bottom    (no JJ separation)
"""

from __future__ import annotations

import pytest

from text_to_gds.device_library import Transmon
from text_to_gds.synthesis import synthesize_transmon
from text_to_gds.verification.connectivity import extract_connectivity


def _topology(tmp_path):
    device = Transmon(frequency_ghz=5.0, anharmonicity_mhz=-250.0)
    gds = tmp_path / "transmon.gds"
    device.geometry().write_gds(gds)
    return extract_connectivity(gds)


def test_transmon_extracts_exactly_one_squid(tmp_path):
    conn = _topology(tmp_path)
    topo = conn["device_topology"]
    assert topo["squid_count"] == 1
    assert topo["junction_count"] == 2
    assert topo["shorted_junctions"] == []


def test_transmon_squid_bridges_two_distinct_islands(tmp_path):
    conn = _topology(tmp_path)
    squid = conn["device_topology"]["squids"][0]
    island_a, island_b = squid["islands"]
    # PASS condition: the two capacitor islands are distinct conductors joined
    # only through the two junctions (no metallic short).
    assert island_a != island_b
    assert len(squid["junction_ids"]) == 2


def test_transmon_every_junction_bridges_two_islands(tmp_path):
    conn = _topology(tmp_path)
    for junction in conn["device_topology"]["junctions"]:
        # A real SIS junction overlaps two distinct metal electrodes.
        assert junction["is_junction"], junction
        assert len(junction["islands"]) == 2


def test_transmon_has_no_floating_metal(tmp_path):
    conn = _topology(tmp_path)
    assert conn["status"] == "passed"
    assert conn["floating_nodes"] == []


def test_transmon_rejects_non_transmon_regime():
    # EJ/EC must stay in [20, 100]; a tiny anharmonicity pushes EJ/EC far above.
    with pytest.raises(ValueError, match="EJ/EC"):
        synthesize_transmon(frequency_ghz=5.0, anharmonicity_mhz=-20.0)
    # A huge anharmonicity drops EJ/EC below the transmon floor.
    with pytest.raises(ValueError, match="EJ/EC"):
        synthesize_transmon(frequency_ghz=5.0, anharmonicity_mhz=-1500.0)
