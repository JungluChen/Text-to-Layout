"""External optional runtime worker. No core import or upstream source vendoring."""

from __future__ import annotations
import hashlib
import importlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.mkdir(exist_ok=False)
    versions = {k: importlib.metadata.version(k) for k in ("quantum-metal", "gdstk")}
    if versions != {"quantum-metal": "0.9.0", "gdstk": "1.0.1"}:
        raise ValueError(f"Unexpected external runtime: {versions}")
    designs = importlib.import_module("qiskit_metal.designs")
    component = importlib.import_module(
        "qiskit_metal.qlibrary.qubits.transmon_pocket"
    ).TransmonPocket
    renderer = importlib.import_module(
        "qiskit_metal.renderers.renderer_gds.gds_renderer"
    ).QGDSRenderer
    d = designs.DesignPlanar()
    d.chips.main.size.size_x = f"{request['chip_width_um']}um"
    d.chips.main.size.size_y = f"{request['chip_height_um']}um"
    options = {
        k.removesuffix("_um"): f"{v}um" for k, v in request.items() if not k.startswith("chip_")
    }
    options.update(pos_x="0um", pos_y="0um", orientation="0", layer="1")
    component(d, "Q1", options=options)
    r = renderer(d)
    r.options.ground_plane = "True"
    r.options.cheese.view_in_file.main = {1: False}
    r.options.no_cheese.view_in_file.main = {1: False}
    r.options.path_filename = ""
    gds = out / "transmon.gds"
    code = r.export_to_gds(str(gds))
    report = {
        "request": request,
        "versions": versions,
        "export_return_code": code,
        "options": r.options,
        "junction_rows": len(d.qgeometry.tables["junction"]),
        "junction_supplied": False,
        "gds_sha256": hashlib.sha256(gds.read_bytes()).hexdigest(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "source_revision": "15587c1284a95354d427540864de4206daa2f064",
        "dependencies": sorted(
            f"{v.metadata['Name']}=={v.version}" for v in importlib.metadata.distributions()
        ),
    }
    (out / "export.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if code == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
