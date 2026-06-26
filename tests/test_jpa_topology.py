"""Geometry-derived topology checks for the lumped-element JPA.

Verifies the canonical flux-driven JPA topology from geometry alone:

        RF feed (M3)
            |  Cc  (coupling-capacitor gap -- NOT galvanic)
        LC node (M2 signal)
          /        \\
       IDC ||      SQUID array
          |          |
        ground (M1) ground

The SQUID provides the DC path signal->ground; the coupling capacitor Cc keeps
the RF feed galvanically isolated from the LC node.
"""

from __future__ import annotations

import pytest

from text_to_gds.device_library import JPA
from text_to_gds.synthesis import synthesize_jpa
from text_to_gds.verification.connectivity import extract_connectivity


def _connectivity(tmp_path):
    device = JPA(frequency_ghz=6.0, impedance_ohm=50.0, target_gain_db=20.0, bandwidth_mhz=200.0)
    gds = tmp_path / "jpa.gds"
    device.geometry().write_gds(gds)
    return extract_connectivity(gds)


def _metal_components(conn):
    """Connected components over conductors, treating junctions as bridges.

    JJ nodes are included so that the two electrodes a junction joins land in the
    same component (the Josephson element carries the DC path of the SQUID).
    """
    metal = {n["id"] for n in conn["nodes"] if n["layer"] in {"M1", "M2", "M3", "VIA12", "VIA23", "JJ"}}
    adj = {m: set() for m in metal}
    for edge in conn["edges"]:
        s, t = edge["source"], edge["target"]
        if edge["kind"] in {"via", "jj_overlap"} and s in adj and t in adj:
            adj[s].add(t)
            adj[t].add(s)
    seen, comps = set(), []
    for node in metal:
        if node in seen:
            continue
        stack, comp = [node], set()
        while stack:
            cur = stack.pop()
            if cur in comp:
                continue
            comp.add(cur)
            seen.add(cur)
            stack.extend(adj[cur] - comp)
        comps.append(comp)
    return comps


def test_jpa_squid_array_is_real(tmp_path):
    topo = _connectivity(tmp_path)["device_topology"]
    assert topo["squid_count"] >= 2
    assert topo["junction_count"] == 2 * topo["squid_count"]
    assert topo["shorted_junctions"] == []


def test_jpa_has_via_stack_to_ground(tmp_path):
    conn = _connectivity(tmp_path)
    via_kinds = [e for e in conn["edges"] if e["kind"] == "via"]
    via12 = [e for e in via_kinds if e["source"].startswith("VIA12")]
    via23 = [e for e in via_kinds if e["source"].startswith("VIA23")]
    # M1<->M2 (ground stack) and M2<->M3 (rail tie-ins) both present.
    assert via12, "expected a VIA12 (M1-M2) connection in the ground stack"
    assert len(via23) >= 2, "expected VIA23 (M2-M3) ties for signal and ground"


def test_jpa_lc_node_connects_to_ground_through_squid(tmp_path):
    conn = _connectivity(tmp_path)
    comps = _metal_components(conn)
    layer_of = {n["id"]: n["layer"] for n in conn["nodes"]}
    # Some component must unite the LC node (M2), the SQUID rails+junctions
    # (M3+JJ) and ground (M1): capacitor LC node and ground joined by the SQUID.
    chain = next(
        (c for c in comps if {"M1", "M2", "M3", "JJ"} <= {layer_of.get(x) for x in c}),
        None,
    )
    assert chain is not None, [sorted({layer_of.get(x) for x in c}) for c in comps]


def test_jpa_no_floating_metal(tmp_path):
    conn = _connectivity(tmp_path)
    assert conn["status"] == "passed"
    assert conn["floating_nodes"] == []


def test_jpa_declared_netlist_has_expected_nets(tmp_path):
    device = JPA()
    names = {net.name for net in device.netlist().nets}
    assert {"rf_feed", "jpa_resonator_node", "ground", "flux_bias"} <= names


def test_jpa_rejects_impossible_gain_bandwidth():
    # sqrt(G)*BW above the carrier has no physical operating point.
    with pytest.raises(ValueError, match="gain-bandwidth"):
        synthesize_jpa(frequency_ghz=6.0, target_gain_db=40.0, bandwidth_mhz=900.0)
    # Bandwidth cannot meet/exceed the carrier.
    with pytest.raises(ValueError, match="bandwidth"):
        synthesize_jpa(frequency_ghz=1.0, target_gain_db=20.0, bandwidth_mhz=2000.0)
