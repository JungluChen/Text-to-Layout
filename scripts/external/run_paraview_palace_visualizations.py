"""Render all declared Palace ParaView views from retained solver arrays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _paraview_common import identity
from textlayout.solvers.palace.paraview import (
    PalaceVisualizationKind,
    ParaViewIdentity,
    render_palace_view,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "external_tools" / "paraview"

VIEWS = {
    PalaceVisualizationKind.AMR_ERROR_INDICATOR: "render_amr_error_indicator.py",
    PalaceVisualizationKind.ELECTRIC_ENERGY_DENSITY: "render_electric_energy_density.py",
    PalaceVisualizationKind.MAGNETIC_ENERGY_DENSITY: "render_magnetic_energy_density.py",
    PalaceVisualizationKind.MESH_QUALITY: "render_mesh_quality.py",
    PalaceVisualizationKind.TARGET_MODE_LOCALIZATION: "render_target_mode_localization.py",
}


def _source(run: Path, kind: PalaceVisualizationKind) -> Path | None:
    patterns = (
        ["**/*error*.pvtu", "**/*error*.vtu"]
        if kind is PalaceVisualizationKind.AMR_ERROR_INDICATOR
        else ["**/*.pvtu", "**/*.vtu", "**/*.vtk"]
    )
    for pattern in patterns:
        matches = sorted(run.glob(pattern))
        if matches:
            return matches[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    run = Path(args.run).resolve()
    installed = identity()
    if installed is None:
        print("ParaView identity is not verified")
        return 1
    pv = ParaViewIdentity(
        version=str(installed["version"]),
        executable=Path(str(installed["executable"])),
        executable_sha256=str(installed["executable_sha256"]),
    )
    output = run / "visualizations"
    results = []
    for kind, script_name in VIEWS.items():
        source = _source(run, kind)
        if source is None:
            print(f"missing retained ParaView source for {kind.value}")
            return 1
        result = render_palace_view(
            pv,
            SCRIPTS / script_name,
            source,
            output / f"{kind.value}.png",
            kind,
        )
        if result.return_code != 0 or result.image_sha256 is None:
            print(f"ParaView render failed for {kind.value}")
            return 1
        results.append(result.model_dump(mode="json"))
    (output / "manifest.json").write_text(
        json.dumps({"schema": "textlayout.palace-paraview.v1", "views": results}, indent=2)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

