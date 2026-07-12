"""Run a real pvpython import/source/write smoke case."""

from __future__ import annotations

import json
import subprocess

from _common import sha256_file
from _paraview_common import SMOKE_ROOT, VERSION, identity, write_json


def main() -> int:
    installed = identity()
    if installed is None:
        print("ParaView is not installed", flush=True)
        return 1
    SMOKE_ROOT.mkdir(parents=True, exist_ok=True)
    script = SMOKE_ROOT / "smoke.py"
    output = SMOKE_ROOT / "sphere.vtp"
    script.write_text(
        "from paraview.simple import Sphere, SaveData\n"
        "source = Sphere(ThetaResolution=8, PhiResolution=8)\n"
        f"SaveData({str(output)!r}, proxy=source)\n",
        encoding="utf-8",
        newline="\n",
    )
    stdout = SMOKE_ROOT / "stdout.txt"
    stderr = SMOKE_ROOT / "stderr.txt"
    completed = subprocess.run(
        [str(installed["executable"]), str(script)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    stdout.write_text(completed.stdout, encoding="utf-8", newline="\n")
    stderr.write_text(completed.stderr, encoding="utf-8", newline="\n")
    if completed.returncode != 0 or not output.is_file():
        print(completed.stderr)
        return 1
    payload = {
        "schema": "textlayout.paraview-smoke.v1",
        "version": VERSION,
        "return_code": completed.returncode,
        "pvpython_sha256": installed["executable_sha256"],
        "script_sha256": sha256_file(script),
        "output_sha256": sha256_file(output),
        "stdout_sha256": sha256_file(stdout),
        "stderr_sha256": sha256_file(stderr),
    }
    write_json(SMOKE_ROOT / "result.json", payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

