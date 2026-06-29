"""Reports package — scientific reports, mask rendering, and solver evidence panels."""

from __future__ import annotations

from text_to_gds.reports.layout_render import (
    render_device_zoom,
    render_layer_legend,
    render_mask_view,
)
from text_to_gds.reports.scientific_report import generate_report
from text_to_gds.reports.solver_panel import (
    check_flat_s_parameters,
    format_panel_text,
    solver_evidence_panel,
    validate_solver_evidence,
)

__all__ = [
    "generate_report",
    "render_mask_view",
    "render_device_zoom",
    "render_layer_legend",
    "solver_evidence_panel",
    "validate_solver_evidence",
    "format_panel_text",
    "check_flat_s_parameters",
]
