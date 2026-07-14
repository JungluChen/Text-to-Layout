"""One-state bounded Palace multimode diagnostic and physical mode catalog."""

from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from textlayout.evidence.canonical import sha256_file
from textlayout.fem import FEMModel
from textlayout.solvers.palace.capability import detect_palace
from textlayout.solvers.palace.config import (
    build_eigenmode_config,
    load_quarter_wave_layout,
    write_config,
    write_json,
)
from textlayout.solvers.palace.mode_classification import (
    classify_mode,
    extract_spatial_energy_fractions,
    ModeSignature,
    select_target_mode,
    TargetModeSelection,
)
from textlayout.solvers.palace.mode_sanity import QuarterWaveSanityResult
from textlayout.solvers.palace.models import PalaceCapability, PalaceOutputError
from textlayout.solvers.palace.overlap import (
    build_material_overlap_map,
    quarter_wave_longitudinal_sanity,
)
from textlayout.solvers.palace.parser import parse_eigenmodes, parse_mode_fields
from textlayout.solvers.palace.runner import run_palace


class DiagnosticMultimodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    output_dir: Path
    mode_catalog: Path | None = None
    selection: TargetModeSelection | None = None
    reason: str | None = None


def _profile_svg(signature: ModeSignature, sanity: QuarterWaveSanityResult) -> str:
    width, height, margin = 900, 440, 50

    def points(values: list[float]) -> str:
        maximum = max(values) or 1.0
        return " ".join(
            f"{margin + index * (width - 2 * margin) / max(len(values) - 1, 1):.3f},"
            f"{height - margin - value / maximum * (height - 2 * margin):.3f}"
            for index, value in enumerate(values)
        )

    return "".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            f'<text x="{margin}" y="30" font-size="20">Mode {signature.mode_index}: '
            f'{signature.frequency_ghz:.9f} GHz - {signature.mode_class}</text>',
            f'<polyline points="{points(sanity.electric_profile)}" fill="none" '
            'stroke="#dc2626" stroke-width="3"/>',
            f'<polyline points="{points(sanity.magnetic_profile)}" fill="none" '
            'stroke="#2563eb" stroke-width="3"/>',
            f'<text x="{margin}" y="{height - 15}" font-size="16" '
            'fill="#dc2626">Electric</text>',
            f'<text x="{margin + 100}" y="{height - 15}" font-size="16" '
            'fill="#2563eb">Magnetic</text>',
            "</svg>",
        ]
    )


def _report(signatures: list[ModeSignature], selection: TargetModeSelection) -> str:
    lines = [
        "# Palace diagnostic multimode classification",
        "",
        f"Status: `{selection.status}`",
        "",
        "| Mode | Frequency (GHz) | Class | Confidence | Physical target |",
        "|---:|---:|---|---:|---|",
    ]
    for signature in signatures:
        lines.append(
            f"| {signature.mode_index} | {signature.frequency_ghz:.9f} | "
            f"{signature.mode_class} | {signature.classification_confidence:.6f} | "
            f"{'yes' if signature.hard_quarter_wave_gates_passed else 'no'} |"
        )
    lines.extend(
        ["", "Frequency proximity did not override a failed physical-shape gate.", ""]
    )
    return "\n".join(lines)


def run_diagnostic_multimode_catalog(
    output_dir: str | Path,
    *,
    layout_path: str | Path,
    mesh_path: str | Path,
    fem_model_path: str | Path,
    capability: PalaceCapability | None = None,
    mode_count: int = 8,
    processes: int = 1,
    timeout_seconds: float = 1200.0,
    max_rss_bytes: int = 7 * 1024**3,
    search_window_ghz: tuple[float, float] = (4.0, 8.0),
) -> DiagnosticMultimodeResult:
    """Execute and classify a genuine one-state Palace diagnostic solve."""
    if not 6 <= mode_count <= 10:
        raise ValueError("diagnostic mode count must be between 6 and 10")
    if processes != 1:
        raise ValueError("diagnostic multimode catalog is bounded to one MPI rank")
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    detected = capability or detect_palace()
    catalog_path = root / "mode_catalog.json"
    if not detected.available:
        write_json(
            {
                "schema": "textlayout.palace-diagnostic-mode-catalog.v1",
                "status": "SKIPPED_SOLVER_ABSENT",
                "reason": detected.unavailable_reason,
            },
            catalog_path,
        )
        return DiagnosticMultimodeResult(
            status="SKIPPED_SOLVER_ABSENT",
            output_dir=root,
            mode_catalog=catalog_path,
            reason=detected.unavailable_reason,
        )
    source_mesh = Path(mesh_path).resolve()
    source_model = Path(fem_model_path).resolve()
    if not source_mesh.is_file() or not source_model.is_file():
        raise FileNotFoundError("diagnostic mesh and FEMModel must exist")
    _, params = load_quarter_wave_layout(layout_path)
    model = FEMModel.model_validate_json(source_model.read_text(encoding="utf-8"))
    model = model.model_copy(
        update={"eigenmode": model.eigenmode.model_copy(update={"mode_count": mode_count})}
    )
    run_dir = root / "solver"
    run_dir.mkdir(parents=True, exist_ok=True)
    retained_mesh = run_dir / source_mesh.name
    if not retained_mesh.is_file() or sha256_file(retained_mesh) != sha256_file(source_mesh):
        shutil.copy2(source_mesh, retained_mesh)
    write_json(model.model_dump(mode="json"), root / "fem_model.json")
    config = build_eigenmode_config(
        model, mesh_filename=retained_mesh.name, output_dir="postpro"
    )
    config["Model"]["Refinement"] = {
        "MaxIts": 0,
        "SaveAdaptIterations": False,
        "SaveAdaptMesh": False,
    }
    config_path = run_dir / "palace_diagnostic.json"
    write_config(config, config_path)
    material_map = build_material_overlap_map(model, config)
    write_json(material_map.model_dump(mode="json"), root / "material_overlap_map.json")
    run = run_palace(
        detected,
        config_path,
        cwd=run_dir,
        processes=processes,
        timeout_seconds=timeout_seconds,
        input_paths=[retained_mesh],
        max_rss_bytes=max_rss_bytes,
    )
    if not run.succeeded:
        reason = (
            "RESOURCE_LIMIT_TERMINATED"
            if run.resource_limit_terminated
            else "SOLVER_TIMEOUT"
            if run.timed_out
            else f"Palace return code {run.return_code}"
        )
        write_json(
            {
                "schema": "textlayout.palace-diagnostic-mode-catalog.v1",
                "status": "SIMULATION_FAILED",
                "reason": reason,
                "run": run.model_dump(mode="json"),
            },
            catalog_path,
        )
        return DiagnosticMultimodeResult(
            status="SIMULATION_FAILED",
            output_dir=root,
            mode_catalog=catalog_path,
            reason=reason,
        )
    postpro = run_dir / "postpro"
    modes = parse_eigenmodes(postpro / "eig.csv")
    if len(modes) != mode_count:
        raise PalaceOutputError(
            f"diagnostic requested {mode_count} modes but parsed {len(modes)}"
        )
    fields = {
        field.mode_index: field
        for field in parse_mode_fields(
            postpro / "domain-E.csv",
            region_names=model.energy_regions(),
            output_dir=postpro,
        )
    }
    endpoint_mesh_size = min(
        refinement.characteristic_length
        for refinement in model.mesh.refinements
        if refinement.target in {"open_end", "grounded_end"}
    )
    gallery = root / "mode_gallery"
    gallery.mkdir(parents=True, exist_ok=True)
    signatures: list[ModeSignature] = []
    sanity_by_mode: dict[int, dict[str, object]] = {}
    for mode in modes:
        field = fields.get(mode.index)
        if field is None or field.field_file is None:
            raise PalaceOutputError(f"diagnostic mode {mode.index} has no retained field")
        sanity = QuarterWaveSanityResult.model_validate(
            quarter_wave_longitudinal_sanity(
                field.field_file,
                material_map=material_map,
                electrical_length=params.length_um,
                local_mesh_size=endpoint_mesh_size,
                conductor_dimension=params.center_width_um,
            )
        )
        spatial = extract_spatial_energy_fractions(
            field.field_file,
            material_map=material_map,
            center_width=params.center_width_um,
            gap=params.gap_um,
            coupling_gap=params.coupling_gap_um,
            electrical_length=params.length_um,
        )
        signature = classify_mode(
            mode_index=mode.index,
            frequency_ghz=mode.frequency_ghz,
            search_window_ghz=search_window_ghz,
            sanity=sanity,
            resonator_localization=field.resonator_localization,
            spatial=spatial,
        )
        signatures.append(signature)
        sanity_by_mode[mode.index] = sanity.model_dump(mode="json", by_alias=True)
        (gallery / f"mode_{mode.index:02d}.svg").write_text(
            _profile_svg(signature, sanity), encoding="utf-8"
        )
    selection = select_target_mode(signatures)
    status = (
        "SIMULATION_INVALID"
        if selection.status == "MODE_CLASSIFICATION_AMBIGUOUS"
        else "OUTPUT_PARSED"
    )
    write_json(
        {
            "schema": "textlayout.palace-diagnostic-mode-catalog.v1",
            "status": status,
            "solver": {
                "name": "Palace",
                "version": detected.version,
                "executable_sha256": detected.executable_sha256,
                "return_code": run.return_code,
                "runtime_seconds": run.runtime_seconds,
                "processes": processes,
            },
            "input_hashes": {
                "mesh": sha256_file(retained_mesh),
                "fem_model": sha256_file(root / "fem_model.json"),
                "config": sha256_file(config_path),
            },
            "candidate_count": len(signatures),
            "signatures": [signature.model_dump(mode="json") for signature in signatures],
            "sanity_by_mode": sanity_by_mode,
            "selection": selection.model_dump(mode="json"),
            "frequency_is_primary_selection_rule": False,
            "raw_fields_retained_locally": True,
        },
        catalog_path,
    )
    (root / "mode_classification_report.md").write_text(
        _report(signatures, selection), encoding="utf-8"
    )
    write_json(
        {
            "schema": "textlayout.palace-diagnostic-run-manifest.v1",
            "status": status,
            "run": run.model_dump(mode="json"),
            "mode_catalog_sha256": sha256_file(catalog_path),
            "gallery_files": sorted(path.name for path in gallery.glob("*.svg")),
        },
        root / "run_manifest.json",
    )
    return DiagnosticMultimodeResult(
        status=status,
        output_dir=root,
        mode_catalog=catalog_path,
        selection=selection,
    )
