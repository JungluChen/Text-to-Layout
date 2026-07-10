"""SuperCAD sequence format — parser, validator, and compiler.

SuperCAD is a plain-text domain-specific format that encodes a superconducting
layout recipe as a parametric sequence.  It compiles to:
  - design_intent.json
  - device.gds  (via a registered LayoutBackend)
  - layout_metadata.json

Format specification
--------------------
DEVICE <type>
TECH <technology_id>

ADD <component> [key=value ...]
ADD <component> [key=value ...]
...

CONSTRAINT <key>=<value>
...

Rules
-----
- DEVICE and TECH are required and must appear before any ADD line.
- Every ADD line must reference a component type that the selected backend
  recognises.  Unknown components → status="unsupported", never fake geometry.
- CONSTRAINT lines are advisory bounds used by the validation skill;
  they are included verbatim in design_intent.json.
- Values may carry SI-prefix units (um, nm, GHz, pF, uA, ohm).
  They are stored as raw strings; the layout backend converts them.
- Blank lines and lines starting with # are ignored.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AddDirective:
    component: str
    params: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"component": self.component, "params": dict(self.params)}


@dataclass
class SuperCADSequence:
    device: str
    technology: str
    directives: list[AddDirective] = field(default_factory=list)
    constraints: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "technology": self.technology,
            "directives": [d.to_dict() for d in self.directives],
            "constraints": dict(self.constraints),
        }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_KV_RE = re.compile(r"(\w+)=(\S+)")


def parse_supercad(text: str) -> SuperCADSequence:
    """Parse a SuperCAD sequence string.  Raises ValueError on syntax errors."""
    device: str | None = None
    technology: str | None = None
    directives: list[AddDirective] = []
    constraints: dict[str, str] = {}

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split(None, 1)
        keyword = parts[0].upper()

        if keyword == "DEVICE":
            if len(parts) < 2:
                raise ValueError(f"Line {lineno}: DEVICE requires a device type")
            device = parts[1].strip()

        elif keyword == "TECH":
            if len(parts) < 2:
                raise ValueError(f"Line {lineno}: TECH requires a technology id")
            technology = parts[1].strip()

        elif keyword == "ADD":
            if len(parts) < 2:
                raise ValueError(f"Line {lineno}: ADD requires a component name")
            rest = parts[1].strip()
            comp_parts = rest.split(None, 1)
            comp_name = comp_parts[0]
            params: dict[str, str] = {}
            if len(comp_parts) > 1:
                for m in _KV_RE.finditer(comp_parts[1]):
                    params[m.group(1)] = m.group(2)
            directives.append(AddDirective(component=comp_name, params=params))

        elif keyword == "CONSTRAINT":
            if len(parts) < 2:
                raise ValueError(f"Line {lineno}: CONSTRAINT requires key=value")
            m = re.match(r"(\w+)=(\S+)", parts[1].strip())
            if not m:
                raise ValueError(f"Line {lineno}: CONSTRAINT must be key=value form")
            constraints[m.group(1)] = m.group(2)

        else:
            raise ValueError(f"Line {lineno}: Unknown keyword '{keyword}'")

    if device is None:
        raise ValueError("SuperCAD sequence missing DEVICE directive")
    if technology is None:
        raise ValueError("SuperCAD sequence missing TECH directive")

    return SuperCADSequence(
        device=device,
        technology=technology,
        directives=directives,
        constraints=constraints,
    )


def parse_supercad_file(path: str | Path) -> SuperCADSequence:
    """Parse a .supercad file from disk."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_supercad(text)


# ---------------------------------------------------------------------------
# Compiler — sequence → design_intent.json + GDS + layout_metadata.json
# ---------------------------------------------------------------------------

def compile_supercad(
    sequence: SuperCADSequence,
    output_dir: str | Path,
    backend_name: str | None = None,
) -> dict[str, Any]:
    """Compile a SuperCAD sequence into design artifacts.

    Parameters
    ----------
    sequence:
        Parsed SuperCADSequence.
    output_dir:
        Directory where outputs are written.
    backend_name:
        Force a specific backend ("kqcircuits", "qiskit_metal", "gdsfactory",
        "local_pcells").  If None, auto-selects by priority.

    Returns
    -------
    dict with keys:
        status          "ok" | "unsupported" | "failed"
        reason          explanation when status != "ok"
        design_intent_path
        gds_path
        layout_metadata_path
        status_path
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    device_slug = re.sub(r"[^a-z0-9_]", "_", sequence.device.lower())

    # --- build design_intent.json -----------------------------------------
    design_intent: dict[str, Any] = {
        "schema": "text-to-gds.design-intent.v1",
        "device": sequence.device,
        "technology": sequence.technology,
        "directives": [d.to_dict() for d in sequence.directives],
        "constraints": sequence.constraints,
        "status": "pending",
    }
    intent_path = out / f"{device_slug}_design_intent.json"
    intent_path.write_text(json.dumps(design_intent, indent=2), encoding="utf-8")

    # --- verify technology YAML exists before touching layout backends -----
    from textlayout._legacy.process import find_technology_yaml

    tech_yaml = find_technology_yaml(sequence.technology)
    if tech_yaml is None:
        result = {
            "status": "failed",
            "reason": (
                f"technology.yaml not found for '{sequence.technology}'. "
                "Layout generation requires a process YAML with layer stack, "
                "materials, thicknesses, and DRC rules. "
                "Add a file to process/<technology_id>.yaml or pass a known technology id."
            ),
            "design_intent_path": str(intent_path),
            "gds_path": None,
            "layout_metadata_path": None,
        }
        _write_status(out / f"{device_slug}_status.json", result)
        return result

    design_intent["technology_yaml"] = str(tech_yaml)

    # --- select layout backend --------------------------------------------
    from textlayout._legacy.layout.backends import select_backend, LayoutBackendError

    components = [d.component for d in sequence.directives]
    try:
        backend = select_backend(
            technology=sequence.technology,
            components=components,
            force=backend_name,
        )
    except LayoutBackendError as exc:
        result = {
            "status": "unsupported",
            "reason": str(exc),
            "design_intent_path": str(intent_path),
            "gds_path": None,
            "layout_metadata_path": None,
        }
        _write_status(out / f"{device_slug}_status.json", result)
        return result

    # --- generate GDS via backend -----------------------------------------
    gds_path = out / f"{device_slug}.gds"
    metadata_path = out / f"{device_slug}_layout_metadata.json"

    try:
        gen_result = backend.generate(
            intent=design_intent,
            gds_path=gds_path,
            metadata_path=metadata_path,
        )
    except Exception as exc:  # noqa: BLE001
        result = {
            "status": "failed",
            "reason": f"Backend '{backend.name}' raised: {exc}",
            "design_intent_path": str(intent_path),
            "gds_path": None,
            "layout_metadata_path": None,
        }
        _write_status(out / f"{device_slug}_status.json", result)
        return result

    # update design_intent with backend info
    design_intent["status"] = "ready"
    design_intent["backend"] = backend.name
    intent_path.write_text(json.dumps(design_intent, indent=2), encoding="utf-8")

    result = {
        "status": "ok",
        "backend": backend.name,
        "design_intent_path": str(intent_path),
        "gds_path": str(gen_result.get("gds_path", gds_path)),
        "layout_metadata_path": str(gen_result.get("metadata_path", metadata_path)),
    }
    _write_status(out / f"{device_slug}_status.json", result)
    return result


def compile_supercad_file(
    supercad_path: str | Path,
    output_dir: str | Path,
    backend_name: str | None = None,
) -> dict[str, Any]:
    """Parse and compile a .supercad file."""
    seq = parse_supercad_file(supercad_path)
    return compile_supercad(seq, output_dir=output_dir, backend_name=backend_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_status(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
