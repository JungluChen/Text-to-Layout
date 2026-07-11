"""Verify the exact Gmsh runtime used to generate Palace meshes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from textlayout.mesh.runtime import gmsh_identity  # noqa: E402


def main() -> int:
    payload = {"schema": "textlayout.gmsh-check.v1", **gmsh_identity()}
    output = ROOT / "out" / "toolchain" / "gmsh_check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
