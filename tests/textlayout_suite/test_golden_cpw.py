"""Golden-layout test: a known CPW DSL must always produce the same geometry.

This pins the deterministic contract DSL → geometry. If a refactor changes the
emitted coordinates, this test fails loudly — which is exactly the safety net the
strangler-fig migration relies on.
"""

from __future__ import annotations

import json

from textlayout import build_default_workflow
from textlayout.schemas.dsl import LayoutSpec

GOLDEN_POLYGONS = [
    {"layer": "M1", "points": [[-5.0, 0.0], [5.0, 0.0], [5.0, 1000.0], [-5.0, 1000.0]]},
    {"layer": "M1", "points": [[-61.0, 0.0], [-11.0, 0.0], [-11.0, 1000.0], [-61.0, 1000.0]]},
    {"layer": "M1", "points": [[11.0, 0.0], [61.0, 0.0], [61.0, 1000.0], [11.0, 1000.0]]},
]


def test_cpw_golden_geometry() -> None:
    workflow = build_default_workflow()
    spec = LayoutSpec(
        component="CPW",
        technology="generic_2metal",
        parameters={
            "center_width_um": 10,
            "gap_um": 6,
            "length_um": 1000,
            "ground_width_um": 50,
            "metal": "M1",
        },
    )
    result = workflow.run(spec, formats=("json",))
    doc = json.loads(result.artifacts["json"])

    assert doc["polygons"] == GOLDEN_POLYGONS
    assert doc["bbox_um"] == {
        "xmin": -61.0,
        "ymin": 0.0,
        "xmax": 61.0,
        "ymax": 1000.0,
        "width": 122.0,
        "height": 1000.0,
    }
