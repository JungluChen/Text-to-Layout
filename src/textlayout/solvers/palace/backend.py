"""End-to-end Palace eigenmode backend and quarter-wave benchmark."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from threading import Event

from textlayout.evidence.canonical import load_canonical, sha256_file, write_canonical
from textlayout.fem import FEMModel
from textlayout.fem.gmsh_physical import GmshMeshResult, mesh_quarter_wave
from textlayout.generators.resonator import QuarterWaveResonatorGenerator
from textlayout.knowledge.technology_library import default_technology_library
from textlayout.models import Geometry
from textlayout.schemas.dsl import QuarterWaveResonatorSpec
from textlayout.solvers.palace.capability import capability_report, detect_palace
from textlayout.solvers.palace.config import (
    build_eigenmode_config,
    deterministic_json_bytes,
    load_quarter_wave_layout,
    quarter_wave_fem_model,
    write_config,
    write_fem_model,
    write_json,
)
from textlayout.solvers.palace.evidence import (
    assess_convergence,
    canonical_evidence,
    track_modes,
)
from textlayout.solvers.palace.models import (
    DomainSweepPoint,
    MeshLevelResult,
    PalaceBenchmarkResult,
    PalaceCapability,
    PalaceOutputError,
    PalaceRun,
)
from textlayout.solvers.palace.parser import (
    field_artifact_files,
    parse_degrees_of_freedom,
    parse_eigenmodes,
    parse_global_error_indicator,
    parse_mode_fields,
)
from textlayout.solvers.palace.runner import run_palace

DEFAULT_LAYOUT = (
    Path(__file__).resolve().parents[4]
    / "examples"
    / "showcase"
    / "05_quarter_wave_resonator_6ghz"
    / "layout.json"
)


def _git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout.strip() or None


class PalaceBackend:
    """A real Palace process boundary; it computes no substitute physics."""

    def __init__(self, capability: PalaceCapability | None = None) -> None:
        self.capability = capability or detect_palace()

    def capability_check(self) -> dict[str, object]:
        return capability_report(self.capability)

    def validate_benchmark_artifacts(
        self,
        output_dir: str | Path,
        *,
        layout_path: str | Path = DEFAULT_LAYOUT,
    ) -> list[str]:
        """Re-derive generated inputs and re-hash every retained artifact."""
        root = Path(output_dir).resolve()
        layout = Path(layout_path).resolve()
        problems: list[str] = []
        fem_path = root / "fem_model.json"
        expected_fem = deterministic_json_bytes(
            quarter_wave_fem_model(layout).model_dump(mode="json")
        )
        if not fem_path.is_file() or fem_path.read_bytes() != expected_fem:
            problems.append("fem_model.json drift")
        manifest_path = root / "mesh_manifest.json"
        if not manifest_path.is_file():
            problems.append("missing mesh_manifest.json")
            return problems
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_tag = {item["tag"]: item for item in manifest}
        for tag, scale in (("mesh_A", 3.5), ("mesh_B", 2.75), ("mesh_C", 1.8)):
            level_dir = root / tag
            mesh_path = level_dir / f"quarter_wave_{tag}.msh"
            entry = by_tag.get(tag)
            if entry is None:
                problems.append(f"missing manifest entry {tag}")
                continue
            if not mesh_path.is_file() or sha256_file(mesh_path) != entry.get("mesh_sha256"):
                problems.append(f"{tag} mesh hash drift")
            model = quarter_wave_fem_model(layout, mesh_scale=scale)
            expected_config = deterministic_json_bytes(
                build_eigenmode_config(
                    model, mesh_filename=mesh_path.name, output_dir="postpro"
                )
            )
            config_path = level_dir / "palace.json"
            if not config_path.is_file() or config_path.read_bytes() != expected_config:
                problems.append(f"{tag} palace.json drift")
        evidence_path = root / "canonical_evidence.json"
        if not evidence_path.is_file():
            problems.append("missing canonical_evidence.json")
        else:
            evidence = load_canonical(evidence_path)
            problems.extend(evidence.verify_output_hashes(root))
        return problems

    def execute(
        self,
        config_path: Path,
        *,
        cwd: Path,
        mesh_path: Path,
        processes: int = 1,
        timeout_seconds: float = 3600.0,
        cancel_event: Event | None = None,
    ) -> PalaceRun:
        return run_palace(
            self.capability,
            config_path,
            cwd=cwd,
            processes=processes,
            timeout_seconds=timeout_seconds,
            cancel_event=cancel_event,
            input_paths=[mesh_path],
        )

    def parse_level(
        self,
        *,
        tag: str,
        model: FEMModel,
        mesh: GmshMeshResult,
        config_path: Path,
        run: PalaceRun,
    ) -> MeshLevelResult:
        if run.timed_out:
            raise PalaceOutputError(f"level {tag}: Palace timed out")
        if run.cancelled:
            raise PalaceOutputError(f"level {tag}: Palace was cancelled")
        if run.return_code != 0:
            raise PalaceOutputError(
                f"level {tag}: Palace returned non-zero exit code {run.return_code}"
            )
        output_name = build_eigenmode_config(
            model, mesh_filename=mesh.path.name, output_dir="postpro"
        )["Problem"]["Output"]
        output_dir = run.output_dir / str(output_name)
        eig_path = output_dir / "eig.csv"
        domain_path = output_dir / "domain-E.csv"
        indicator_path = output_dir / "error-indicators.csv"
        modes = parse_eigenmodes(eig_path)
        fields = parse_mode_fields(
            domain_path,
            region_names=model.energy_regions(),
            output_dir=output_dir,
        )
        global_error = parse_global_error_indicator(indicator_path)
        dof = parse_degrees_of_freedom(output_dir, run.stdout_path)
        required = [eig_path, domain_path, indicator_path]
        for field in fields:
            if field.field_file is not None:
                required.extend(field_artifact_files(field.field_file))
        output_hashes = {
            str(path.resolve().relative_to(run.output_dir.resolve())): sha256_file(path)
            for path in required
        }
        local_sizes = {
            refinement.target: refinement.characteristic_length
            for refinement in model.mesh.refinements
        }
        return MeshLevelResult(
            tag=tag,
            characteristic_length_um=model.mesh.characteristic_length,
            local_characteristic_lengths_um=local_sizes,
            element_count=mesh.element_count,
            degrees_of_freedom=dof,
            minimum_quality=mesh.minimum_quality,
            mean_quality=mesh.mean_quality,
            mesh_path=mesh.path,
            mesh_sha256=sha256_file(mesh.path),
            mesh_runtime_seconds=mesh.runtime_seconds,
            solver_runtime_seconds=run.runtime_seconds,
            command=run.command,
            return_code=run.return_code,
            stdout_path=run.stdout_path,
            stderr_path=run.stderr_path,
            config_path=config_path,
            eig_path=eig_path,
            domain_energy_path=domain_path,
            error_indicator_path=indicator_path,
            modes=modes,
            mode_fields=fields,
            global_error_indicator_percent=global_error,
            output_file_hashes=output_hashes,
        )

    def _prepare_level(
        self,
        *,
        tag: str,
        layout_path: Path,
        geometry: Geometry,
        params: QuarterWaveResonatorSpec,
        output_dir: Path,
        mesh_scale: float,
        domain_scale: float,
    ) -> tuple[FEMModel, GmshMeshResult, Path]:
        level_dir = output_dir / tag
        level_dir.mkdir(parents=True, exist_ok=True)
        model = quarter_wave_fem_model(
            layout_path, mesh_scale=mesh_scale, domain_scale=domain_scale
        )
        mesh = mesh_quarter_wave(
            geometry,
            params,
            model,
            level_dir / f"quarter_wave_{tag}.msh",
            domain_scale=domain_scale,
        )
        config_path = level_dir / "palace.json"
        write_config(
            build_eigenmode_config(
                model, mesh_filename=mesh.path.name, output_dir="postpro"
            ),
            config_path,
        )
        return model, mesh, config_path

    def _execute_prepared_level(
        self,
        *,
        tag: str,
        model: FEMModel,
        mesh: GmshMeshResult,
        config_path: Path,
        processes: int,
        timeout_seconds: float,
        cancel_event: Event | None,
    ) -> MeshLevelResult:
        run = self.execute(
            config_path,
            cwd=config_path.parent,
            mesh_path=mesh.path,
            processes=processes,
            timeout_seconds=timeout_seconds,
            cancel_event=cancel_event,
        )
        return self.parse_level(
            tag=tag, model=model, mesh=mesh, config_path=config_path, run=run
        )

    def run_quarter_wave_benchmark(
        self,
        output_dir: str | Path,
        *,
        layout_path: str | Path = DEFAULT_LAYOUT,
        processes: int = 1,
        timeout_seconds: float = 7200.0,
        cancel_event: Event | None = None,
    ) -> PalaceBenchmarkResult:
        """Prepare and, when available, execute the 6 GHz vertical slice."""
        root = Path(output_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        layout = Path(layout_path).resolve()
        spec, params = load_quarter_wave_layout(layout)
        technology = default_technology_library().get(spec.technology)
        geometry = QuarterWaveResonatorGenerator().generate(
            params, technology, spec.origin
        )
        base_model = quarter_wave_fem_model(layout)
        fem_path = root / "fem_model.json"
        fem_hash = write_fem_model(base_model, fem_path)
        write_json(self.capability_check(), root / "palace_capability.json")

        prepared: list[tuple[str, FEMModel, GmshMeshResult, Path]] = []
        mesh_manifest: list[dict[str, object]] = []
        for tag, scale in (("mesh_A", 3.5), ("mesh_B", 2.75), ("mesh_C", 1.8)):
            model, mesh, config_path = self._prepare_level(
                tag=tag,
                layout_path=layout,
                geometry=geometry,
                params=params,
                output_dir=root,
                mesh_scale=scale,
                domain_scale=1.0,
            )
            prepared.append((tag, model, mesh, config_path))
            mesh_manifest.append(
                {
                    "tag": tag,
                    "characteristic_length_um": model.mesh.characteristic_length,
                    "local_characteristic_lengths_um": {
                        item.target: item.characteristic_length
                        for item in model.mesh.refinements
                    },
                    "element_count": mesh.element_count,
                    "minimum_quality": mesh.minimum_quality,
                    "mean_quality": mesh.mean_quality,
                    "mesh_sha256": sha256_file(mesh.path),
                    "runtime_seconds": mesh.runtime_seconds,
                }
            )
        mesh_manifest_path = root / "mesh_manifest.json"
        write_json(mesh_manifest, mesh_manifest_path)

        if not self.capability.available:
            evidence = canonical_evidence(
                design_id="quarter_wave_resonator_6ghz_palace",
                design_hash=sha256_file(layout),
                geometry_hash=None,
                fem_model_hash=fem_hash,
                capability=self.capability,
                levels=[],
                report=None,
                domain_sweep=[],
                output_root=root,
                target_frequency_ghz=None,
                git_commit=_git_commit(Path(__file__).resolve().parents[4]),
            )
            evidence_path = write_canonical(evidence, root / "canonical_evidence.json")
            engineering = root / "engineering_report.md"
            mesh_rows = "\n".join(
                "| {} | {:.6g} | {} | {:.6g} | {:.6g} | {:.3f} |".format(
                    str(item["tag"]),
                    float(str(item["characteristic_length_um"])),
                    int(str(item["element_count"])),
                    float(str(item["minimum_quality"])),
                    float(str(item["mean_quality"])),
                    float(str(item["runtime_seconds"])),
                )
                for item in mesh_manifest
            )
            engineering.write_text(
                "# Palace quarter-wave resonator engineering report\n\n"
                f"Status: `{evidence.status.value}`\n\n"
                "Three physical Gmsh meshes and deterministic Palace configurations were "
                "generated from the committed 6 GHz layout. Palace was unavailable, so no "
                "solver-owned output exists and no eigenfrequency was extracted.\n\n"
                "| Mesh | global length (um) | tetrahedra | min quality | mean quality | mesh runtime (s) |\n"
                "| --- | ---: | ---: | ---: | ---: | ---: |\n"
                f"{mesh_rows}\n\n"
                "Degrees of freedom, eigenmodes, mode overlap, and convergence are absent "
                "because those are Palace-owned results.\n",
                encoding="utf-8",
                newline="\n",
            )
            return PalaceBenchmarkResult(
                status=evidence.status.value,
                output_dir=root,
                capability=self.capability,
                fem_model_path=fem_path,
                mesh_manifest_path=mesh_manifest_path,
                evidence_path=evidence_path,
                engineering_report_path=engineering,
                reason=self.capability.unavailable_reason,
            )

        levels = [
            self._execute_prepared_level(
                tag=tag,
                model=model,
                mesh=mesh,
                config_path=config_path,
                processes=processes,
                timeout_seconds=timeout_seconds,
                cancel_event=cancel_event,
            )
            for tag, model, mesh, config_path in prepared
        ]
        tracking_error = None
        try:
            tracked, matches = track_modes(levels, seed_frequency_ghz=6.0)
        except PalaceOutputError as exc:
            tracked, matches, tracking_error = [], [], str(exc)

        domain_levels: list[MeshLevelResult] = []
        for scale in (0.85, 1.0, 1.15):
            if scale == 1.0:
                domain_levels.append(levels[-1])
                continue
            tag = f"domain_{scale:.2f}".replace(".", "p")
            model, mesh, config_path = self._prepare_level(
                tag=tag,
                layout_path=layout,
                geometry=geometry,
                params=params,
                output_dir=root,
                mesh_scale=1.8,
                domain_scale=scale,
            )
            domain_levels.append(
                self._execute_prepared_level(
                    tag=tag,
                    model=model,
                    mesh=mesh,
                    config_path=config_path,
                    processes=processes,
                    timeout_seconds=timeout_seconds,
                    cancel_event=cancel_event,
                )
            )
        domain_points = [
            DomainSweepPoint(
                scale=scale,
                frequency_ghz=min(
                    level.modes, key=lambda mode: abs(mode.frequency_ghz - 6.0)
                ).frequency_ghz,
                output_file_hashes={
                    f"{level.tag}/{name}": digest
                    for name, digest in level.output_file_hashes.items()
                },
            )
            for scale, level in zip((0.85, 1.0, 1.15), domain_levels)
        ]
        report = assess_convergence(
            levels,
            tracked_mode_indices=tracked,
            matches=matches,
            domain_sweep=domain_points,
            search_window_ghz=(base_model.eigenmode.target_frequency_ghz, 12.0),
            tracking_error=tracking_error,
        )
        tracking_path = root / "mode_tracking_report.json"
        mesh_report_path = root / "mesh_convergence_report.json"
        domain_report_path = root / "domain_convergence_report.json"
        write_json(
            {
                "tracked_mode_indices": tracked,
                "matches": [item.model_dump(mode="json") for item in matches],
                "error": tracking_error,
            },
            tracking_path,
        )
        write_json(report.model_dump(mode="json"), mesh_report_path)
        write_json(
            [point.model_dump(mode="json") for point in domain_points], domain_report_path
        )
        geometry_path = layout.parent / "output.gds"
        evidence = canonical_evidence(
            design_id="quarter_wave_resonator_6ghz_palace",
            design_hash=sha256_file(layout),
            geometry_hash=sha256_file(geometry_path) if geometry_path.is_file() else None,
            fem_model_hash=fem_hash,
            capability=self.capability,
            levels=levels,
            report=report,
            domain_sweep=domain_points,
            output_root=root,
            target_frequency_ghz=None,
            target_method=None,
            git_commit=_git_commit(Path(__file__).resolve().parents[4]),
        )
        evidence_path = write_canonical(evidence, root / "canonical_evidence.json")
        engineering = root / "engineering_report.md"
        engineering.write_text(
            "# Palace quarter-wave resonator engineering report\n\n"
            f"Status: `{evidence.status.value}`\n\n"
            f"Finest tracked frequency: `{report.finest_frequency_ghz}` GHz\n\n"
            "This result has no independent reference artifact. Even when every "
            "convergence gate passes, it is limited to `SIMULATION_EXECUTED`.\n\n"
            "## Gates\n\n"
            + "\n".join(
                f"- {'PASS' if gate.passed else 'FAIL'} `{gate.name}`: {gate.detail}"
                for gate in report.gates
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return PalaceBenchmarkResult(
            status=evidence.status.value,
            output_dir=root,
            capability=self.capability,
            fem_model_path=fem_path,
            mesh_manifest_path=mesh_manifest_path,
            mesh_levels=levels,
            evidence_path=evidence_path,
            mode_tracking_report_path=tracking_path,
            mesh_convergence_report_path=mesh_report_path,
            domain_convergence_report_path=domain_report_path,
            engineering_report_path=engineering,
        )
