from pathlib import Path

import meshio
import numpy as np

from textlayout.solvers.palace.models import MaterialOverlapEntry, MaterialOverlapMap
from textlayout.solvers.palace.overlap import centroid_projected_energy_mac


def _map() -> MaterialOverlapMap:
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return MaterialOverlapMap(
        model_sha256="a" * 64,
        palace_config_sha256="b" * 64,
        entries=[
            MaterialOverlapEntry(
                attribute=1,
                material_name="vacuum",
                permittivity=identity,
                permeability=identity,
                source="test",
                model_sha256="a" * 64,
                critical_region=True,
            )
        ],
        map_sha256="c" * 64,
    )


def _parallel_fixture(root: Path, *, ghost_second: bool) -> Path:
    points = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    field = np.tile([1.0, 0.0, 0.0], (4, 1))
    for rank in range(2):
        meshio.write(
            root / f"proc{rank:06d}.vtu",
            meshio.Mesh(
                points,
                [("tetra", np.asarray([[0, 1, 2, 3]]))],
                point_data={
                    "E_real": field,
                    "E_imag": np.zeros_like(field),
                    "B_real": field,
                    "B_imag": np.zeros_like(field),
                },
                cell_data={
                    "attribute": [np.asarray([1], np.int32)],
                    "vtkGhostType": [np.asarray([1 if ghost_second and rank else 0], np.uint8)],
                    "GlobalCellIds": [np.asarray([7], np.int64)],
                },
            ),
            binary=True,
        )
    manifest = root / "data.pvtu"
    manifest.write_text(
        '<VTKFile><PUnstructuredGrid><Piece Source="proc000000.vtu"/>'
        '<Piece Source="proc000001.vtu"/></PUnstructuredGrid></VTKFile>',
        encoding="utf-8",
    )
    return manifest


def test_mpi_ghost_cells_are_removed(tmp_path: Path) -> None:
    fixture = _parallel_fixture(tmp_path, ghost_second=True)
    result = centroid_projected_energy_mac(
        fixture, fixture, kind="electric", material_map=_map()
    )
    assert result.raw_cell_count == 2
    assert result.ghost_cells_removed == 1
    assert result.duplicate_cells_removed == 0
    assert result.integration_cell_count == 1


def test_mpi_duplicate_global_cells_are_removed(tmp_path: Path) -> None:
    fixture = _parallel_fixture(tmp_path, ghost_second=False)
    result = centroid_projected_energy_mac(
        fixture, fixture, kind="electric", material_map=_map()
    )
    assert result.raw_cell_count == 2
    assert result.ghost_cells_removed == 0
    assert result.duplicate_cells_removed == 1
    assert result.raw_total_volume == 2 * result.deduplicated_total_volume
