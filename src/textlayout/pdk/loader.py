"""Load a :class:`PDK` from a YAML or JSON file, with full Pydantic validation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from textlayout.pdk.models import PDK


def load_pdk(path: str | Path) -> PDK:
    """Parse a PDK definition file. Raises on any schema violation — no partial loads."""
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif file_path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"unsupported PDK file extension: {file_path.suffix!r} ({file_path})")
    return PDK.model_validate(data)


def write_pdk(pdk: PDK, path: str | Path) -> Path:
    """Write a PDK to YAML (round-trippable with :func:`load_pdk`)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(pdk.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
    return out
