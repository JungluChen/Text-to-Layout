from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from text_to_gds.process import DEFAULT_PROCESS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_TOOLS_ROOT = Path(os.environ.get("TEXT_TO_GDS_TOOLS", PROJECT_ROOT / ".tools")).resolve()


def _numbers(text: str) -> list[float]:
    # KLayout geometry strings may use scientific notation (e.g. 1.2e-05).
    return [
        float(match)
        for match in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", text)
    ]


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

        # The KLayout report database carries no explicit severity; decks
        # conventionally encode warning-level rules in the category name.
        category_text = f"{category['name']} {category['description']}".lower()
        severity = "warning" if "warn" in category_text else "error"
        violations.append(
            {
                "rule": category["name"],
                "message": category["description"],
                "severity": severity,
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


def resolve_klayout_executable(klayout_executable: str = "klayout") -> str | None:
    """Resolve a KLayout executable from explicit path, PATH, env, or local .tools."""
    path = Path(klayout_executable)
    if path.exists():
        return str(path.resolve())
    path_match = shutil.which(klayout_executable)
    if path_match:
        return path_match
    default_names = {"klayout", "klayout.exe", "klayout_app", "klayout_app.exe"}
    if Path(klayout_executable).name not in default_names:
        return None
    if os.environ.get("TEXT_TO_GDS_KLAYOUT"):
        env_path = Path(os.environ["TEXT_TO_GDS_KLAYOUT"])
        if env_path.exists():
            return str(env_path.resolve())
    for candidate in sorted(LOCAL_TOOLS_ROOT.glob("klayout-*/klayout_app.exe"), reverse=True):
        if candidate.exists():
            return str(candidate.resolve())
    for candidate in sorted(LOCAL_TOOLS_ROOT.glob("klayout-*/**/klayout_app.exe"), reverse=True):
        if candidate.exists():
            return str(candidate.resolve())
    return None


def run_external_klayout_drc(
    *,
    gds_path: str | Path,
    deck_path: str | Path,
    lyrdb_path: str | Path,
    klayout_executable: str = "klayout",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Run a KLayout DRC deck in batch mode when the executable is available."""
    executable = resolve_klayout_executable(klayout_executable)
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

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {
            "engine": "klayout_external",
            "executed": False,
            "command": command,
            "returncode": None,
            "stdout": stdout,
            "stderr": stderr,
            "warnings": [f"KLayout DRC timed out after {timeout_seconds} s."],
        }
    return {
        "engine": "klayout_external",
        "executed": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "warnings": [] if completed.returncode == 0 else ["KLayout DRC command failed."],
    }


def _segment_distance_um(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> float:
    """Min distance between two non-intersecting segments (attained at an endpoint)."""

    def point_segment(p: tuple[float, float], s1: tuple[float, float], s2: tuple[float, float]) -> float:
        dx, dy = s2[0] - s1[0], s2[1] - s1[1]
        length_sq = dx * dx + dy * dy
        if length_sq <= 0.0:
            return ((p[0] - s1[0]) ** 2 + (p[1] - s1[1]) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((p[0] - s1[0]) * dx + (p[1] - s1[1]) * dy) / length_sq))
        cx, cy = s1[0] + t * dx, s1[1] + t * dy
        return ((p[0] - cx) ** 2 + (p[1] - cy) ** 2) ** 0.5

    return min(
        point_segment(a1, b1, b2),
        point_segment(a2, b1, b2),
        point_segment(b1, a1, a2),
        point_segment(b2, a1, a2),
    )


def _edge_pair_violation(
    pair: Any,
    *,
    rule: str,
    process_name: str,
    kind: str,
    dbu: float,
    cell: str,
    layer: tuple[int, int],
    limit_um: float,
) -> dict[str, Any]:
    """Normalize one KLayout width/space edge-pair marker into a violation dict."""
    bbox = pair.bbox()
    first, second = pair.first, pair.second
    measured_um = _segment_distance_um(
        (first.p1.x * dbu, first.p1.y * dbu),
        (first.p2.x * dbu, first.p2.y * dbu),
        (second.p1.x * dbu, second.p1.y * dbu),
        (second.p2.x * dbu, second.p2.y * dbu),
    )
    return {
        "rule": rule,
        "message": (
            f"{process_name} {kind} {measured_um:.6g} um is below {limit_um:.6g} um."
        ),
        "severity": "error",
        "cell": cell,
        "layer": [int(layer[0]), int(layer[1])],
        "bbox_um": [
            float(bbox.left) * dbu,
            float(bbox.bottom) * dbu,
            float(bbox.right) * dbu,
            float(bbox.top) * dbu,
        ],
        "measured_um": measured_um,
        "limit_um": limit_um,
    }


def run_python_process_drc(gds_path: str | Path) -> dict[str, Any]:
    """Run starter process rules with the Python KLayout module.

    This is not a foundry signoff deck. It is a deterministic headless fallback for
    local-first agent loops when an external KLayout GUI distribution is unavailable
    or cannot execute Ruby DRC decks on the host.

    Checks are polygon-exact: shapes are merged per layer under each top cell and
    verified with KLayout's ``Region.width_check`` / ``Region.space_check``
    (Euclidean metric), so concave polygons, diagonal edges, and interleaved comb
    structures are measured correctly. ``checked_shapes`` counts drawn shapes fed
    into the checks; ``checked_spacing_pairs`` counts merged polygons on layers
    where a spacing rule applies.
    """
    try:
        import klayout.db as kdb
    except ImportError:
        return {
            "engine": "klayout_python_process_rules",
            "executed": False,
            "passed": False,
            "checked_shapes": 0,
            "checked_spacing_pairs": 0,
            "violations": [],
            "warnings": ["KLayout Python module is unavailable; process-rule fallback skipped."],
        }

    layout = kdb.Layout()
    layout.read(str(gds_path))
    dbu = float(layout.dbu)
    specs_by_layer = {
        layer_spec.layer: layer_spec
        for layer_spec in DEFAULT_PROCESS.layers.values()
        if layer_spec.min_width_um > 0.0 or layer_spec.min_spacing_um > 0.0
    }
    layer_indexes = {
        (int(layout.get_info(index).layer), int(layout.get_info(index).datatype)): index
        for index in layout.layer_indices()
    }

    violations: list[dict[str, Any]] = []
    checked_shapes = 0
    checked_spacing_pairs = 0

    for layer, spec in specs_by_layer.items():
        layer_index = layer_indexes.get(layer)
        if layer_index is None:
            continue

        # Flatten under each top cell so inter-cell geometry is checked too.
        for top in layout.top_cells():
            region = kdb.Region(top.begin_shapes_rec(layer_index))
            drawn_count = region.count()
            if drawn_count == 0:
                continue
            checked_shapes += drawn_count
            region.merge()

            if spec.min_width_um > 0.0:
                limit_dbu = int(round(spec.min_width_um / dbu))
                for pair in region.width_check(limit_dbu).each():
                    violations.append(
                        _edge_pair_violation(
                            pair,
                            rule=f"{spec.name}_min_width",
                            process_name=spec.name,
                            kind="width",
                            dbu=dbu,
                            cell=top.name,
                            layer=layer,
                            limit_um=spec.min_width_um,
                        )
                    )

            if spec.min_spacing_um > 0.0:
                checked_spacing_pairs += region.count()
                limit_dbu = int(round(spec.min_spacing_um / dbu))
                for pair in region.space_check(limit_dbu).each():
                    violations.append(
                        _edge_pair_violation(
                            pair,
                            rule=f"{spec.name}_min_space",
                            process_name=spec.name,
                            kind="spacing",
                            dbu=dbu,
                            cell=top.name,
                            layer=layer,
                            limit_um=spec.min_spacing_um,
                        )
                    )

    return {
        "engine": "klayout_python_process_rules",
        "executed": True,
        "passed": not any(v["severity"] == "error" for v in violations),
        "checked_shapes": checked_shapes,
        "checked_spacing_pairs": checked_spacing_pairs,
        "violations": violations,
        "warnings": [],
    }
