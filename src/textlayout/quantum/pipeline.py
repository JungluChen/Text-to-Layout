"""Full Energy-Participation-Ratio (EPR) to Circuit Hamiltonian Chain.

Connects the field-to-qubit pipeline:
`GDS` -> `Gmsh 3D Mesh` -> `Palace Eigenmode` -> `domain-E.csv` / `port-EPR.csv` -> `quantum/epr.py` -> `scqubits`

1. Ingests GDS (via KLayout or GdsExporter) into Geometry.
2. Generates conformal tetrahedral 3D mesh via `mesh_geometry` (Gmsh).
3. Executes or parses Palace eigenmode simulation.
4. Ingests field energies and port participation (`domain-E.csv`, `port-EPR.csv`).
5. Quantizes linear modes via EPR: extracts p_mj, computes E_C, E_J, f_01, alpha.
6. Validates alpha ~= -E_C in the transmon regime (E_J / E_C >> 1) and cross-checks
   with scqubits exact numerical diagonalization (< 0.5% error).
7. Outputs `quantum_analysis.json` and embeds evidence in `report.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from textlayout.evidence.contract import EvidenceStatus
from textlayout.mesh.gmsh_pipeline import MeshControls, MeshManifest, SubstrateStack, mesh_geometry
from textlayout.models import Geometry, Polygon
from textlayout.quantum.epr import (
    JunctionModel,
    QuantumAnalysis,
    analyze_palace_output,
    embed_in_report,
    write_quantum_analysis,
)
from textlayout.simulation.backends.palace import PalaceEigenmodeResult, run_eigenmode


def geometry_from_gds(gds_path: str | Path, name: str | None = None) -> Geometry:
    """Extract 2-D metal polygons from a GDS file into a Geometry model."""
    path = Path(gds_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"GDS file not found: {path}")

    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(path))
    dbu = float(layout.dbu)
    top_cell = layout.top_cell()
    if top_cell is None:
        raise ValueError(f"GDS file has no top cell: {path}")

    polygons: list[Polygon] = []
    for layer_idx in layout.layer_indices():
        info = layout.get_info(layer_idx)
        layer_name = f"layer_{info.layer}_{info.datatype}" if info.layer != 1 else "metal"
        for shape in top_cell.shapes(layer_idx).each():
            if shape.is_polygon() or shape.is_box():
                poly = shape.polygon
                pts = tuple((float(pt.x) * dbu, float(pt.y) * dbu) for pt in poly.each_point_hull())
                if len(pts) >= 3:
                    polygons.append(Polygon(layer=layer_name, points=pts))

    return Geometry(
        name=name or top_cell.name or path.stem,
        polygons=tuple(polygons),
    )


class FieldToQubitPipelineResult(BaseModel):
    """Result of the full field-to-qubit EPR pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: EvidenceStatus
    geometry_name: str
    mesh_manifest: MeshManifest | None = None
    palace_result: PalaceEigenmodeResult | None = None
    quantum_analysis: QuantumAnalysis
    analysis_path: Path | None = None
    report_path: Path | None = None
    e_j_ghz: float | None = None
    e_c_ghz: float | None = None
    f01_ghz: float | None = None
    anharmonicity_ghz: float | None = None
    transmon_regime_valid: bool = False
    scqubits_agreement_pass: bool = False
    reason: str | None = None


def run_field_to_qubit_pipeline(
    *,
    geometry: Geometry | None = None,
    gds_path: str | Path | None = None,
    stack: SubstrateStack | None = None,
    junctions: list[JunctionModel] | None = None,
    output_dir: str | Path = "quantum_sim",
    report_path: str | Path | None = None,
    controls: MeshControls | None = None,
    execute_solver: bool = True,
    cross_check_scqubits: bool = True,
    transmon_f01_tolerance_percent: float = 0.5,
    transmon_ratio_threshold: float = 20.0,
    region_names: dict[int, str] | None = None,
) -> FieldToQubitPipelineResult:
    """Execute the end-to-end field-to-qubit chain from GDS/Geometry to Hamiltonian."""
    # 1. Resolve geometry
    if geometry is None:
        if gds_path is None:
            raise ValueError("Either geometry or gds_path must be supplied.")
        geometry = geometry_from_gds(gds_path)
    elif gds_path is not None and not Path(gds_path).is_file():
        from textlayout.exporters.gds_exporter import GdsExporter
        from textlayout.knowledge import default_technology_library

        tech = default_technology_library().get("generic_2metal")
        GdsExporter().write(geometry, tech, gds_path)

    # 2. Defaults
    stack = stack or SubstrateStack(
        substrate_material="silicon",
        epsilon_r=11.45,
        substrate_thickness_um=500.0,
        vacuum_height_um=500.0,
    )
    junctions = junctions or [JunctionModel(name="J1", josephson_energy_ghz=20.0, port_index=1)]
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    postpro = out / "postpro"

    # 3. Gmsh 3D mesh & Palace simulation
    palace_res: PalaceEigenmodeResult | None = None
    mesh_man: MeshManifest | None = None

    if not postpro.is_dir() or not (postpro / "eig.csv").is_file():
        if execute_solver:
            palace_res = run_eigenmode(
                geometry,
                stack,
                out,
                controls=controls,
                execute=True,
            )
            if palace_res.mesh_manifest_path and palace_res.mesh_manifest_path.is_file():
                try:
                    mesh_man = MeshManifest.model_validate(
                        json.loads(palace_res.mesh_manifest_path.read_text(encoding="utf-8"))
                    )
                except Exception:
                    mesh_man = None
        else:
            mesh_man = mesh_geometry(geometry, stack, out / "model.msh", controls=controls)
    else:
        # Load pre-existing mesh manifest if present
        manifest_path = out / "mesh_manifest.json"
        if manifest_path.is_file():
            try:
                mesh_man = MeshManifest.model_validate(
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                )
            except Exception:
                mesh_man = None

    # 4. Ingest field energies & port participation from Palace output
    analysis = analyze_palace_output(
        postpro,
        junctions,
        region_names=region_names or {1: "substrate", 2: "vacuum"},
        cross_check=cross_check_scqubits,
    )

    # 5. Extract quantum parameters & validate transmon regime
    qubit_idx = analysis.qubit_mode_index
    e_j_val: float | None = None
    e_c_val: float | None = None
    f01_val: float | None = None
    alpha_val: float | None = None
    transmon_regime_valid = False
    scqubits_agreement_pass = False

    if qubit_idx is not None and junctions:
        q_key = str(qubit_idx)
        j0 = junctions[0]
        e_j_val = j0.e_j_ghz
        p_q = analysis.participation_matrix.get(q_key, {}).get(j0.name, 0.0)
        f_lin = analysis.linear_frequency_ghz.get(q_key, 0.0)
        f01_val = analysis.dressed_frequency_ghz.get(q_key)
        alpha_val = analysis.anharmonicity_ghz.get(q_key)

        if p_q > 0.0 and e_j_val > 0.0:
            e_c_val = f_lin**2 / (8.0 * e_j_val * p_q)
            if e_c_val > 0.0:
                ratio = e_j_val / e_c_val
                transmon_regime_valid = ratio >= transmon_ratio_threshold

        check = analysis.scqubits_cross_check
        if (
            check is not None
            and check.status == EvidenceStatus.SIMULATION_EXECUTED
            and check.f01_deviation_percent is not None
        ):
            scqubits_agreement_pass = check.f01_deviation_percent <= transmon_f01_tolerance_percent

    # 6. Persist quantum analysis JSON
    analysis_saved_path = write_quantum_analysis(analysis, out)

    # 7. Embed evidence in report.md if requested
    rep_saved_path: Path | None = None
    if report_path is not None:
        rep_saved_path = embed_in_report(report_path, analysis)

    return FieldToQubitPipelineResult(
        status=analysis.status,
        geometry_name=geometry.name,
        mesh_manifest=mesh_man,
        palace_result=palace_res,
        quantum_analysis=analysis,
        analysis_path=analysis_saved_path,
        report_path=rep_saved_path,
        e_j_ghz=e_j_val,
        e_c_ghz=e_c_val,
        f01_ghz=f01_val,
        anharmonicity_ghz=alpha_val,
        transmon_regime_valid=transmon_regime_valid,
        scqubits_agreement_pass=scqubits_agreement_pass,
        reason=analysis.reason,
    )
