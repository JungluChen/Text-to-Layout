"""Check pinned ParaView executable identity and retained smoke evidence."""

from __future__ import annotations

import json

from _common import sha256_file
from _paraview_common import SMOKE_ROOT, VERSION, identity


def check() -> dict[str, object]:
    installed = identity()
    smoke = SMOKE_ROOT / "result.json"
    smoke_valid = False
    if installed is not None and smoke.is_file():
        payload = json.loads(smoke.read_text(encoding="utf-8"))
        output = SMOKE_ROOT / "sphere.vtp"
        smoke_valid = (
            payload.get("pvpython_sha256") == installed["executable_sha256"]
            and output.is_file()
            and payload.get("output_sha256") == sha256_file(output)
            and payload.get("version") == VERSION
        )
    return {
        "schema": "textlayout.paraview-check.v1",
        "state": (
            "SMOKE_TEST_PASSED"
            if smoke_valid
            else "IDENTITY_VERIFIED"
            if installed is not None
            else "REGISTERED"
        ),
        "identity": installed,
        "smoke_valid": smoke_valid,
    }


def main() -> int:
    payload = check()
    print(json.dumps(payload, indent=2))
    return 0 if payload["state"] in {"IDENTITY_VERIFIED", "SMOKE_TEST_PASSED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

