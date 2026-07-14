from __future__ import annotations

import json
from pathlib import Path

import pytest

from textlayout.exporters.gds_exporter import canonicalize_gds, GdsExporter
from textlayout.generators.resonator import QuarterWaveResonatorGenerator
from textlayout.knowledge import default_technology_library
from textlayout.models import Geometry
from textlayout.solvers.palace.backend import DEFAULT_LAYOUT
from textlayout.solvers.palace.config import (
    build_eigenmode_config,
    load_quarter_wave_layout,
    quarter_wave_fem_model,
)
from textlayout.solvers.palace.model_audit import (
    audit_quarter_wave_model,
    render_quarter_wave_audit_svg,
)
from textlayout.solvers.palace.models import PalaceOutputError


def _inputs():
    spec, params = load_quarter_wave_layout(DEFAULT_LAYOUT)
    technology = default_technology_library().get(spec.technology)
    geometry = QuarterWaveResonatorGenerator().generate(params, technology, spec.origin)
    model = quarter_wave_fem_model(DEFAULT_LAYOUT)
    return params, technology, geometry, model


def test_model_audit_cross_checks_real_gds_and_boundaries(tmp_path: Path) -> None:
    params, technology, geometry, model = _inputs()
    gds = canonicalize_gds(
        GdsExporter().write(geometry, technology, tmp_path / "resonator.gds"),
        cell_name="QUARTER_WAVE_AUDIT",
    )
    resolved = tmp_path / "resolved.json"
    resolved.write_text(
        json.dumps(
            build_eigenmode_config(model, mesh_filename="mesh.msh", output_dir="postpro")
        ),
        encoding="utf-8",
    )
    audit = audit_quarter_wave_model(
        geometry,
        params,
        model,
        technology,
        gds_path=gds,
        resolved_config_path=resolved,
    )
    assert audit.status == "PASS"
    assert all(check.passed for check in audit.klayout_connectivity_checks)
    assert audit.physical_grounded_end_um == (0.0, 0.0)
    assert audit.physical_open_end_um == (0.0, params.length_um)
    assert audit.palace_boundary_cross_check["interface_attributes_in_pec"] == []
    assert audit.gds_cross_check["passed"] is True
    assert "GROUNDED" in render_quarter_wave_audit_svg(geometry, audit)


def test_missing_endpoint_metadata_fails_closed() -> None:
    params, technology, geometry, model = _inputs()
    metadata = dict(geometry.metadata)
    metadata.pop("physical_open_end_um")
    invalid = Geometry(
        name=geometry.name,
        polygons=geometry.polygons,
        ports=geometry.ports,
        metadata=metadata,
    )
    with pytest.raises(PalaceOutputError, match="physical open end"):
        audit_quarter_wave_model(invalid, params, model, technology)


def test_swapped_endpoint_metadata_fails_closed() -> None:
    params, technology, geometry, model = _inputs()
    metadata = dict(geometry.metadata)
    metadata["physical_grounded_end_um"] = metadata["physical_open_end_um"]
    metadata["physical_open_end_um"] = geometry.metadata["physical_grounded_end_um"]
    invalid = Geometry(
        name=geometry.name,
        polygons=geometry.polygons,
        ports=geometry.ports,
        metadata=metadata,
    )
    with pytest.raises(PalaceOutputError, match="centreline endpoint order"):
        audit_quarter_wave_model(invalid, params, model, technology)
