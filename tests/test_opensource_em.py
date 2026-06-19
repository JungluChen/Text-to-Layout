from __future__ import annotations

import json

import klayout.db as kdb

from text_to_gds.elmer_bridge import build_elmer_sif, write_elmer_project
from text_to_gds.meshing import write_stack_mesh
from text_to_gds.palace_bridge import build_palace_config, write_palace_project
from text_to_gds.parasitics import export_fastcap, export_fasthenry


def _make_gds(path):
    layout = kdb.Layout()
    layout.dbu = 0.001
    top = layout.create_cell("TOP")
    # 100 um x 20 um traces on M1 (3/0) and M3 (6/0); coords in dbu (1 um = 1000 dbu).
    top.shapes(layout.layer(3, 0)).insert(kdb.Box(0, 0, 100000, 20000))
    top.shapes(layout.layer(6, 0)).insert(kdb.Box(0, 30000, 100000, 50000))
    layout.write(str(path))
    return path


def test_gmsh_mesh_runs_or_skips_cleanly(tmp_path):
    gds = _make_gds(tmp_path / "dev.gds")
    r = write_stack_mesh(gds, mesh_path=tmp_path / "dev.msh", report_path=tmp_path / "dev.mesh.json")
    assert r["status"] in {"executed", "skipped"}
    if r["status"] == "executed":
        assert r["tetrahedra"] > 0 and r["nodes"] > 0
        assert (tmp_path / "dev.msh").exists()


def test_palace_config_and_project(tmp_path):
    config = build_palace_config(mesh_path="dev.msh", substrate={"relative_permittivity": 11.45}, num_modes=4)
    assert config["Problem"]["Type"] == "Eigenmode"
    assert config["Solver"]["Eigenmode"]["N"] == 4

    gds = _make_gds(tmp_path / "dev.gds")
    r = write_palace_project(
        gds,
        config_path=tmp_path / "dev.palace.json",
        report_path=tmp_path / "dev.palace.report.json",
        mesh_path=tmp_path / "dev.msh",
        mesh_report_path=tmp_path / "dev.mesh.json",
    )
    assert r["status"] == "prepared"
    assert "frequency_ghz" in r["expected_results"]
    written = json.loads((tmp_path / "dev.palace.json").read_text(encoding="utf-8"))
    assert written["Model"]["Mesh"] == "dev.msh"


def test_elmer_sif_and_project(tmp_path):
    sif = build_elmer_sif(relative_permittivity=11.45, capacitance_bodies=3)
    assert "StatElecSolver" in sif and "Calculate Capacitance Matrix = True" in sif

    gds = _make_gds(tmp_path / "dev.gds")
    r = write_elmer_project(
        gds,
        sif_path=tmp_path / "dev.sif",
        report_path=tmp_path / "dev.elmer.json",
        mesh_path=tmp_path / "dev.msh",
        mesh_report_path=tmp_path / "dev.mesh.json",
    )
    assert r["status"] == "prepared"
    assert (tmp_path / "dev.sif").read_text(encoding="utf-8").startswith("! Text-to-GDS")


def test_fasthenry_and_fastcap_generate_decks(tmp_path):
    gds = _make_gds(tmp_path / "dev.gds")
    fh = export_fasthenry(gds, inp_path=tmp_path / "dev.inp", report_path=tmp_path / "dev.fh.json", run=True)
    assert fh["status"] in {"skipped", "executed"}
    deck = (tmp_path / "dev.inp").read_text(encoding="utf-8")
    assert ".units um" in deck and ".freq" in deck and ".external" in deck

    fc = export_fastcap(gds, lst_path=tmp_path / "dev.lst", report_path=tmp_path / "dev.fc.json", run=True)
    assert fc["status"] in {"skipped", "executed"}
    assert (tmp_path / "dev.lst").exists()
    assert any(p.suffix == ".qui" for p in tmp_path.iterdir())
