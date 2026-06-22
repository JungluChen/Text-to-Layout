"""Layout understanding: GDS -> circuit elements, device classification, novelty.

Wraps the existing polygon-connectivity extractor so the review committee and
the orchestrator can reason about *what was actually drawn* (junctions, nets,
vias) rather than just the sidecar metadata. GDS similarity/novelty is computed
against an optional reference corpus and degrades cleanly when none is supplied
(item 14, learning from a real corpus, stays data-gated).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from text_to_gds.process import DEFAULT_PROCESS, ProcessStack
from text_to_gds.verification import extract_circuit_from_gds

_DEVICE_KEYWORDS = (
    ("squid", "dc_squid"),
    ("jpa", "jpa"),
    ("twpa", "twpa"),
    ("transmon", "transmon"),
    ("qubit", "transmon"),
    ("resonator", "resonator"),
    ("cpw", "cpw"),
    ("coplanar", "cpw"),
    ("idc", "idc"),
    ("interdigital", "idc"),
    ("meander", "inductor"),
    ("via", "via_chain"),
    ("junction", "josephson_junction"),
    ("jj", "josephson_junction"),
)


def _classify(pcell: str, element_kinds: list[str]) -> str:
    key = str(pcell or "").lower()
    for keyword, label in _DEVICE_KEYWORDS:
        if keyword in key:
            return label
    if "josephson_junction" in element_kinds:
        return "josephson_junction"
    return "unknown"


def summarize_layout(
    gds_path: str | Path,
    *,
    sidecar: dict[str, Any] | None = None,
    process: ProcessStack = DEFAULT_PROCESS,
) -> dict[str, Any]:
    """Extract the circuit and classify the device drawn in a GDS."""
    circuit = extract_circuit_from_gds(gds_path, process=process)
    element_kinds = sorted({element["kind"] for element in circuit["elements"]})
    junctions = [e for e in circuit["elements"] if e["kind"] == "josephson_junction"]
    pcell = (sidecar or {}).get("pcell", "")
    device_class = _classify(pcell, element_kinds)
    return {
        "schema": "text-to-gds.layout-understanding.v1",
        "source_gds": str(gds_path),
        "device_class": device_class,
        "element_kinds": element_kinds,
        "junction_count": len(junctions),
        "net_count": len(circuit["nodes"]),
        "elements": circuit["elements"],
        "polygon_connectivity_complete": circuit["polygon_connectivity_complete"],
        "feature_vector": [
            float(len(junctions)),
            float(len(circuit["nodes"])),
            float(len(element_kinds)),
        ],
    }


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("feature vectors must have equal length")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def layout_novelty(
    feature_vector: list[float],
    corpus: list[dict[str, Any]] | None = None,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """Rank similarity against a reference corpus and report a novelty score.

    ``corpus`` is a list of ``{"name": str, "vector": list[float]}``. With no
    corpus the result is honest about it (novelty is undefined, not 100%).
    """
    if not corpus:
        return {
            "schema": "text-to-gds.layout-novelty.v1",
            "corpus_size": 0,
            "matches": [],
            "novelty_pct": None,
            "note": "No reference corpus supplied; novelty cannot be computed (item 14 is data-gated).",
        }
    scored = [
        {"name": entry["name"], "similarity_pct": round(_cosine(feature_vector, entry["vector"]) * 100.0, 1)}
        for entry in corpus
        if "vector" in entry
    ]
    scored.sort(key=lambda item: item["similarity_pct"], reverse=True)
    best = scored[0]["similarity_pct"] if scored else 0.0
    return {
        "schema": "text-to-gds.layout-novelty.v1",
        "corpus_size": len(corpus),
        "matches": scored[:limit],
        "novelty_pct": round(100.0 - best, 1),
    }
