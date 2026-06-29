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
import json
from pathlib import Path

from textlayout.errors import UnknownComponentError, UnknownExporterError
from textlayout.exporters.gds_exporter import GdsExporter
from textlayout.geometry.engine import GeometryEngine
from textlayout.models import Geometry, Technology
from textlayout.ports.exporter import Exporter
from textlayout.research import ResearchReport, research
from textlayout.schemas.dsl import LayoutSpec
from textlayout.verification import Check, CheckStatus, VerificationContext, VerificationReport, Verifier


@dataclass(frozen=True, slots=True)
class GenerateResult:
    """Outcome of a generate run — pure data, ready to serialise to JSON."""

    spec: LayoutSpec
    geometry: Geometry
    report: VerificationReport
    research: ResearchReport
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

        if spec.component not in self._engine.components:
            raise UnknownComponentError(spec.component, self._engine.components)
        technology = self._engine.technology(spec.technology)
        research_report = research(spec, technology)
        build = self._engine.build(spec)
        ctx = VerificationContext(
            spec=spec,
            params=build.params,
            geometry=build.geometry,
            technology=build.technology,
            component_built=True,
        )
        pre_export_report = self._with_evidence_checks(
            self._verifier.verify(ctx), research_report
        )

        # Geometry that fails verification is diagnostic only. It is never
        # rendered or written as a final artifact.
        if not pre_export_report.passed:
            return GenerateResult(
                spec=spec,
                geometry=build.geometry,
                report=pre_export_report,
                research=research_report,
            )

        pre_export_report = self._with_exporter_sanity(
            pre_export_report,
            formats,
            build.geometry,
            build.technology,
        )
        if not pre_export_report.passed:
            return GenerateResult(
                spec=spec,
                geometry=build.geometry,
                report=pre_export_report,
                research=research_report,
            )

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

        report = pre_export_report
        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
            support = self._write_support_files(
                out=out,
                stem=stem,
                spec=spec,
                geometry=build.geometry,
                research_report=research_report,
                verification=pre_export_report,
                geometry_files=files,
            )
            files.update(support)
            report = self._with_artifact_checks(pre_export_report, files)
            verification_path = Path(files["verification"])
            verification_path.write_text(
                json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
            Path(files["report"]).write_text(
                _render_report(spec, build.geometry, research_report, report, files),
                encoding="utf-8",
            )

        return GenerateResult(
            spec=spec,
            geometry=build.geometry,
            report=report,
            research=research_report,
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

    def technology(self, name: str) -> Technology:
        return self._engine.technology(name)

    def research_only(self, spec: LayoutSpec) -> ResearchReport:
        """Produce the pre-layout evidence report without generating geometry."""
        return research(spec, self._engine.technology(spec.technology))

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

    @staticmethod
    def _with_evidence_checks(
        report: VerificationReport, research_report: ResearchReport
    ) -> VerificationReport:
        references_ok = bool(research_report.references)
        equations_ok = bool(research_report.equations)
        simulation_ok = bool(research_report.simulation_recommendation)
        added = (
            Check(
                "research_evidence",
                CheckStatus.PASS if references_ok and equations_ok else CheckStatus.FAIL,
                "" if references_ok and equations_ok else "Research requires equations and references.",
            ),
            Check(
                "simulation_workflow_documented",
                CheckStatus.PASS if simulation_ok else CheckStatus.FAIL,
                "" if simulation_ok else "No simulation workflow is documented.",
            ),
        )
        return VerificationReport.from_checks(report.component, (*report.checks, *added))

    @staticmethod
    def _with_artifact_checks(
        report: VerificationReport, files: Mapping[str, str]
    ) -> VerificationReport:
        checks = list(report.checks)
        for kind, filename in files.items():
            path = Path(filename)
            ok = path.is_file() and path.stat().st_size > 0
            checks.append(
                Check(
                    name=f"output_{kind}_exists",
                    status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                    message="" if ok else f"Expected output is missing or empty: {path}",
                )
            )
        gds_path = files.get("gds")
        if gds_path is not None:
            try:
                import klayout.db as kdb

                layout = kdb.Layout()
                layout.read(gds_path)
                top_cells = layout.top_cells()
                ok = bool(top_cells) and any(cell.bbox().area() > 0 for cell in top_cells)
                message = "" if ok else "KLayout readback found no non-empty top cell."
            except Exception as exc:  # pragma: no cover - defensive backend boundary
                ok = False
                message = f"KLayout GDS readback failed: {exc}"
            checks.append(
                Check(
                    name="klayout_gds_readback",
                    status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                    message=message,
                )
            )
        return VerificationReport.from_checks(report.component, checks)

    def _with_exporter_sanity(
        self,
        report: VerificationReport,
        formats: Sequence[str],
        geometry: Geometry,
        technology: Technology,
    ) -> VerificationReport:
        if "gds" not in formats:
            return report
        exporter = self._exporters["gds"]
        if not isinstance(exporter, GdsExporter):
            return VerificationReport.from_checks(
                report.component,
                (*report.checks, Check("gdsfactory_component_sanity", CheckStatus.FAIL, "GDS exporter is not gdsfactory-backed.")),
            )
        try:
            component = exporter.build_component(geometry, technology)
            polygon_count = sum(len(polygons) for polygons in component.get_polygons(by="tuple").values())
            ok = polygon_count > 0 and len(component.ports) == len(geometry.ports)
            message = "" if ok else "gdsfactory component lost polygons or ports during lowering."
        except Exception as exc:  # pragma: no cover - backend defensive boundary
            ok = False
            message = f"gdsfactory component construction failed: {exc}"
        return VerificationReport.from_checks(
            report.component,
            (
                *report.checks,
                Check(
                    "gdsfactory_component_sanity",
                    CheckStatus.PASS if ok else CheckStatus.FAIL,
                    message,
                ),
            ),
        )

    @staticmethod
    def _write_support_files(
        *,
        out: Path,
        stem: str,
        spec: LayoutSpec,
        geometry: Geometry,
        research_report: ResearchReport,
        verification: VerificationReport,
        geometry_files: Mapping[str, str],
    ) -> dict[str, str]:
        layout_path = out / f"{stem}.layout.json"
        verification_path = out / f"{stem}.verification.json"
        evidence_path = out / f"{stem}.evidence.md"
        analytical_path = out / f"{stem}.analytical_estimate.md"
        simulation_plan_path = out / f"{stem}.simulation_plan.md"
        report_path = out / f"{stem}.report.md"
        layout_path.write_text(
            json.dumps(spec.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
        )
        verification_path.write_text(
            json.dumps(verification.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
        evidence_path.write_text(research_report.to_markdown(), encoding="utf-8")
        analytical_path.write_text(
            research_report.analytical_estimate_markdown(), encoding="utf-8"
        )
        simulation_plan_path.write_text(
            research_report.simulation_plan_markdown(), encoding="utf-8"
        )
        report_path.write_text(
            _render_report(
                spec,
                geometry,
                research_report,
                verification,
                {
                    **geometry_files,
                    "layout_dsl": str(layout_path),
                    "evidence": str(evidence_path),
                    "analytical_estimate": str(analytical_path),
                    "simulation_plan": str(simulation_plan_path),
                },
            ),
            encoding="utf-8",
        )
        return {
            "layout_dsl": str(layout_path),
            "verification": str(verification_path),
            "evidence": str(evidence_path),
            "analytical_estimate": str(analytical_path),
            "simulation_plan": str(simulation_plan_path),
            "report": str(report_path),
        }


def _render_report(
    spec: LayoutSpec,
    geometry: Geometry,
    research_report: ResearchReport,
    verification: VerificationReport,
    files: Mapping[str, str],
) -> str:
    bbox = geometry.bbox()
    lines = [
        f"# Layout Report - {spec.component}",
        "",
        f"- Verification: **{verification.status.upper()}**",
        f"- Technology: `{spec.technology}`",
        f"- Bounding box: `{bbox.width:.4f} um x {bbox.height:.4f} um`",
        f"- Polygons: `{len(geometry.polygons)}`",
        f"- Ports: `{len(geometry.ports)}`",
        "",
        "## Target and analytical model",
        "",
        f"- Model: {research_report.model_name}",
    ]
    for key, value in research_report.physical_target.items():
        lines.append(f"- Target `{key}`: `{value}`")
    for key, value in research_report.analytical_estimates.items():
        lines.append(f"- Estimate `{key}`: `{value}`")
    lines += ["", "## Verification", ""]
    for check in verification.checks:
        lines.append(f"- `{check.status.value.upper()}` {check.name}" + (f": {check.message}" if check.message else ""))
    lines += ["", "## Artifacts", ""]
    for kind, filename in files.items():
        lines.append(f"- `{kind}`: `{filename}`")
    lines += [
        "",
        "## Simulation status",
        "",
        "No EM solver was executed by this workflow. The analytical estimate is a design starting point only.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in research_report.limitations)
    return "\n".join(lines).rstrip() + "\n"
