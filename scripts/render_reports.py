"""Regenerate report/example artifacts without fake solver results.

This wrapper is intentionally small. The report renderer lives in
``scripts.generate_assets.generate_sims`` and already labels unavailable solver
panels as skipped or input-prepared instead of plotting synthetic physics.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reexec_with_uv_if_needed(exc: ModuleNotFoundError) -> None:
    if os.environ.get("TEXT_TO_GDS_UV_REEXEC") == "1":
        raise exc
    env = dict(os.environ)
    env["TEXT_TO_GDS_UV_REEXEC"] = "1"
    cmd = ["py", "-3", "-m", "uv", "run", "--no-sync", "python", str(Path(__file__).resolve())]
    raise SystemExit(subprocess.call(cmd, cwd=ROOT, env=env))


def main() -> None:
    try:
        from scripts.generate_assets import ASSETS, WORKSPACE, generate_sims
    except ModuleNotFoundError as exc:
        _reexec_with_uv_if_needed(exc)

    try:
        generate_sims()
    except ModuleNotFoundError as exc:
        _reexec_with_uv_if_needed(exc)
    report_assets = [
        ASSETS / "scientific_report_example.png",
        ASSETS / "openems_extraction_example.png",
    ]
    manifest = {
        "schema": "text-to-gds.report-render.v1",
        "status": "generated",
        "workspace": str(WORKSPACE),
        "assets": [str(path) for path in report_assets if path.is_file()],
        "reports": [str(path) for path in sorted(WORKSPACE.glob("*.report.json"))],
    }
    manifest_path = WORKSPACE / "report_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
