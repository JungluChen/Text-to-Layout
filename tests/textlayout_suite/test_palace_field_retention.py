from pathlib import Path

from textlayout.solvers.palace.retention import apply_field_retention


def _manifest(path: Path, piece: str) -> None:
    path.write_text(
        f'<VTKFile><PUnstructuredGrid><Piece Source="{piece}"/></PUnstructuredGrid></VTKFile>',
        encoding="utf-8",
    )


def test_retention_keeps_target_and_competitor_and_records_deletions(tmp_path: Path) -> None:
    fields: dict[int, Path] = {}
    for mode in (1, 2, 3):
        piece = tmp_path / f"mode{mode}.vtu"
        piece.write_text("field", encoding="utf-8")
        manifest = tmp_path / f"mode{mode}.pvtu"
        _manifest(manifest, piece.name)
        fields[mode] = manifest
    result = apply_field_retention(
        tmp_path,
        [fields],
        target_modes=[2],
        competitor_modes=[1],
    )
    assert result.is_file()
    assert fields[1].exists() and fields[2].exists()
    assert not fields[3].exists() and not (tmp_path / "mode3.vtu").exists()
