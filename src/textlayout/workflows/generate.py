"""GenerateWorkflow — the deterministic DSL→artifacts use-case.

Pipeline (the safe IC-layout contract):

    DSL  →  GeometryEngine  →  Verifier  →  Exporters

It is AI-free: given a valid :class:`LayoutSpec` it builds geometry, verifies it
against design rules, and renders the requested artifacts. Text artifacts
(JSON, SVG) are returned inline; binary artifacts (GDS) are written to
``output_dir`` when one is supplied. The agent layer's job is only to *produce*
the spec; this workflow turns it into trustworthy, verified artifacts.

All collaborators are injected (engine, verifier, exporters) — no global state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from textlayout.errors import UnknownExporterError
from textlayout.geometry.engine import GeometryEngine
from textlayout.models import Geometry
from textlayout.ports.exporter import Exporter
from textlayout.schemas.dsl import LayoutSpec
from textlayout.verification import VerificationContext, VerificationReport, Verifier


@dataclass(frozen=True, slots=True)
class GenerateResult:
    """Outcome of a generate run — pure data, ready to serialise to JSON."""

    spec: LayoutSpec
    geometry: Geometry
    report: VerificationReport
    artifacts: Mapping[str, str] = field(default_factory=dict)
    files: Mapping[str, str] = field(default_factory=dict)

    @property
    def summary(self) -> dict[str, object]:
        bbox = None if self.geometry.is_empty else self.geometry.bbox()
        return {
            "component": self.spec.component,
            "technology": self.spec.technology,
            "layers": list(self.geometry.layers()),
            "polygon_count": len(self.geometry.polygons),
            "port_count": len(self.geometry.ports),
            "bbox_um": None
            if bbox is None
            else {"width": round(bbox.width, 4), "height": round(bbox.height, 4)},
            "verification_status": self.report.status,
        }


class GenerateWorkflow:
    """Orchestrates build → verify → export for one :class:`LayoutSpec`."""

    def __init__(
        self,
        engine: GeometryEngine,
        verifier: Verifier,
        exporters: Mapping[str, Exporter],
    ) -> None:
        self._engine = engine
        self._verifier = verifier
        self._exporters = dict(exporters)

    def run(
        self,
        spec: LayoutSpec,
        formats: Sequence[str] | None = None,
        output_dir: str | Path | None = None,
        stem: str | None = None,
    ) -> GenerateResult:
        formats = list(formats) if formats is not None else spec.requested_formats()
        unknown = [f for f in formats if f not in self._exporters]
        if unknown:
            raise UnknownExporterError(unknown[0], list(self._exporters))

        build = self._engine.build(spec)
        ctx = VerificationContext(
            spec=spec,
            params=build.params,
            geometry=build.geometry,
            technology=build.technology,
            component_built=True,
        )
        report = self._verifier.verify(ctx)

        out = Path(output_dir) if output_dir is not None else None
        stem = stem or spec.component.lower()
        artifacts: dict[str, str] = {}
        files: dict[str, str] = {}

        for fmt in formats:
            exporter = self._exporters[fmt]
            if not exporter.binary:
                artifacts[fmt] = exporter.render(build.geometry, build.technology)
            if out is not None:
                path = out / f"{stem}.{exporter.extension}"
                files[fmt] = str(exporter.write(build.geometry, build.technology, path))

        return GenerateResult(
            spec=spec,
            geometry=build.geometry,
            report=report,
            artifacts=artifacts,
            files=files,
        )

    @property
    def export_formats(self) -> list[str]:
        return sorted(self._exporters)

    @property
    def component_names(self) -> list[str]:
        return self._engine.components

    @property
    def technology_names(self) -> list[str]:
        return self._engine.technologies

    def verify_only(self, spec: LayoutSpec) -> VerificationReport:
        """Build + verify without exporting (powers POST /layout/verify)."""
        build = self._engine.build(spec)
        ctx = VerificationContext(
            spec=spec,
            params=build.params,
            geometry=build.geometry,
            technology=build.technology,
        )
        return self._verifier.verify(ctx)
