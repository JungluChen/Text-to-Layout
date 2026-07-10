"""Generated handoffs for proprietary electromagnetic solvers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textlayout._legacy.pyaedt_bridge import write_hfss_project_bridge

__all__ = ["write_hfss_project_bridge", "write_sonnet_project_bridge"]


def write_sonnet_project_bridge(
    gds_path: str | Path,
    *,
    script_path: str | Path,
    report_path: str | Path,
    output_project_path: str | Path,
) -> dict[str, Any]:
    """Write a SonnetLab MATLAB import/analysis script."""
    gds = Path(gds_path).resolve()
    script, report, output = Path(script_path), Path(report_path), Path(output_project_path)
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        f'''% Generated Text-to-GDS SonnetLab handoff.
project = SonnetProject();
project.importGDS('{str(gds).replace(chr(92), "/")}');
project.addFrequencySweep(1.0, 12.0, 0.05);
project.saveAs('{str(output.resolve()).replace(chr(92), "/")}');
disp(project.FileName);
''',
        encoding="utf-8",
    )
    result = {
        "schema": "text-to-gds.sonnet-bridge.v1",
        "status": "prepared",
        "source_gds": str(gds),
        "script_path": str(script),
        "expected_project_path": str(output),
        "report_path": str(report),
        "backend": "Sonnet Suites via SonnetLab",
        "validity": "Generated bridge; requires Sonnet Suites and SonnetLab.",
    }
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
