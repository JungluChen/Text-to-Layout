from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


def _numbers(text: str) -> list[float]:
    return [float(match) for match in re.findall(r"-?\d+(?:\.\d+)?", text)]


def _bbox_from_geometry_text(text: str) -> list[float] | None:
    values = _numbers(text)
    if len(values) < 4 or len(values) % 2 != 0:
        return None
    xs = values[0::2]
    ys = values[1::2]
    return [min(xs), min(ys), max(xs), max(ys)]


def _xml_text(node: ElementTree.Element | None, default: str = "") -> str:
    if node is None:
        return default
    text = "".join(node.itertext()).strip()
    return text or default


def parse_lyrdb_report(lyrdb_path: str | Path) -> list[dict[str, Any]]:
    """Parse a KLayout report database into normalized DRC violations."""
    root = ElementTree.parse(lyrdb_path).getroot()

    categories: dict[str, dict[str, str]] = {}
    for category in root.findall(".//category"):
        category_id = category.attrib.get("id", "")
        name = _xml_text(category.find("name"), category_id or "unknown")
        description = _xml_text(category.find("description"), name)
        if category_id:
            categories[category_id] = {"name": name, "description": description}

    cells: dict[str, str] = {}
    for cell in root.findall(".//cell"):
        cell_id = cell.attrib.get("id", "")
        if cell_id:
            cells[cell_id] = _xml_text(cell.find("name"), cell_id)

    violations: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        category_key = _xml_text(item.find("category"))
        cell_key = _xml_text(item.find("cell"))
        category = categories.get(category_key, {"name": category_key, "description": category_key})
        values = []
        bbox_um = None
        for value in item.findall(".//value"):
            geometry_text = _xml_text(value)
            if geometry_text:
                values.append(geometry_text)
                bbox_um = bbox_um or _bbox_from_geometry_text(geometry_text)

        violations.append(
            {
                "rule": category["name"],
                "message": category["description"],
                "severity": "error",
                "cell": cells.get(cell_key, cell_key),
                "bbox_um": bbox_um,
                "geometry": values,
            }
        )
    return violations


def parse_json_drc_report(json_path: str | Path) -> list[dict[str, Any]]:
    """Parse an existing JSON DRC report or a list of normalized violations."""
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        violations = payload.get("violations", [])
        if isinstance(violations, list):
            return violations
    raise ValueError(f"Unsupported JSON DRC report shape: {json_path}")


def parse_drc_report(report_path: str | Path) -> list[dict[str, Any]]:
    path = Path(report_path)
    suffix = path.suffix.lower()
    if suffix == ".lyrdb":
        return parse_lyrdb_report(path)
    if suffix == ".json":
        return parse_json_drc_report(path)
    raise ValueError(f"Unsupported DRC report format: {path}")


def run_external_klayout_drc(
    *,
    gds_path: str | Path,
    deck_path: str | Path,
    lyrdb_path: str | Path,
    klayout_executable: str = "klayout",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Run a KLayout DRC deck in batch mode when the executable is available."""
    executable = shutil.which(klayout_executable) or (
        str(Path(klayout_executable)) if Path(klayout_executable).exists() else None
    )
    command = [
        executable or klayout_executable,
        "-b",
        "-rd",
        f"input={Path(gds_path)}",
        "-rd",
        f"report={Path(lyrdb_path)}",
        "-r",
        str(deck_path),
    ]

    if executable is None:
        return {
            "engine": "klayout_external",
            "executed": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "warnings": [f"KLayout executable not found: {klayout_executable}"],
        }

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        "engine": "klayout_external",
        "executed": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "warnings": [] if completed.returncode == 0 else ["KLayout DRC command failed."],
    }
