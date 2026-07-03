from __future__ import annotations

from pathlib import Path

from textlayout.models import Geometry, rectangle
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation.palace import prepare_palace_fullchip


def test_palace_path_prepares_geo_and_config_without_solver(tmp_path: Path) -> None:
    geometry = Geometry("tile", (rectangle("M1", 0, 0, 100, 20),))
    spec = LayoutSpec(component="TestChip", parameters={})
    result = prepare_palace_fullchip(
        spec,
        geometry,
        tmp_path,
        execute=True,
        palace_executable="missing-palace-test-binary",
        gmsh_executable="missing-gmsh-test-binary",
    )
    assert result.status == "input_files_prepared"
    assert result.solver_executed is False
    assert Path(result.artifacts["gmsh_geo"]).is_file()
    assert Path(result.artifacts["palace_config"]).is_file()
    assert "Physical Volume(1)" in Path(result.artifacts["gmsh_geo"]).read_text(
        encoding="utf-8"
    )
