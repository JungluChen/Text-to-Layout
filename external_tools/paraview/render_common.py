"""Shared headless ParaView render implementation for Palace arrays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from paraview.simple import (  # type: ignore[import-not-found]
    ColorBy,
    GetColorTransferFunction,
    Hide,
    MeshQuality,
    OpenDataFile,
    Render,
    SaveScreenshot,
    Show,
    _DisableFirstRenderCameraReset,
)


def _arrays(source) -> tuple[list[str], list[str]]:
    source.UpdatePipeline()
    return sorted(source.PointData.keys()), sorted(source.CellData.keys())


def main(
    kind: str,
    candidates: tuple[str, ...],
    *,
    mesh_quality: bool = False,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _DisableFirstRenderCameraReset()
    source = OpenDataFile(str(source_path))
    rendered = MeshQuality(Input=source) if mesh_quality else source
    if mesh_quality:
        Hide(source)
    point_arrays, cell_arrays = _arrays(rendered)
    selected = "Quality" if mesh_quality else next(
        (name for name in candidates if name in point_arrays or name in cell_arrays),
        None,
    )
    if selected is None:
        raise RuntimeError(
            f"{kind}: none of {candidates!r} found; point={point_arrays}, cell={cell_arrays}"
        )
    association = "POINTS" if selected in point_arrays else "CELLS"
    display = Show(rendered)
    ColorBy(display, (association, selected))
    GetColorTransferFunction(selected).RescaleTransferFunctionToDataRange(True, False)
    Render()
    SaveScreenshot(str(output_path), ImageResolution=[1600, 1000])
    output_path.with_suffix(".render.json").write_text(
        json.dumps(
            {
                "kind": kind,
                "input": str(source_path),
                "output": str(output_path),
                "association": association,
                "selected_array": selected,
                "point_arrays": point_arrays,
                "cell_arrays": cell_arrays,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0

