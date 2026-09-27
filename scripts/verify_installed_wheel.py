"""Install a wheel into a clean venv and retain real outside-checkout CLI transcripts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import venv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    results = []
    with tempfile.TemporaryDirectory(prefix="textlayout-installed-") as folder:
        root = Path(folder)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        bindir = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
        python = bindir / ("python.exe" if os.name == "nt" else "python")
        cli = bindir / ("textlayout.exe" if os.name == "nt" else "textlayout")
        env["MPLCONFIGDIR"] = str(root / "matplotlib")
        commands = [
            ("install", [str(python), "-m", "pip", "install", str(wheel)]),
            ("identity", [str(python), "-c", "import textlayout,importlib.metadata; print(textlayout.__file__); print(importlib.metadata.version('text-to-gds'))"]),
            ("help", [str(cli), "--help"]),
            ("doctor", [str(cli), "doctor", "--json"]),
            ("prompt", [str(cli), "prompt", "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um minimum gap, 4 um finger width, and two RF ports.", "--out", str(out / "prompt")]),
            ("reference", [str(cli), "verify", "--reference", "--cache", str(root / "cache"), "--out", str(out / "reference")]),
        ]
        for name, command in commands:
            log = out / f"{name}.log"
            try:
                process = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=600, check=False)
                text = process.stdout + "\n--- STDERR ---\n" + process.stderr
                code = process.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                text = str(exc)
                code = -1
            log.write_text(text, encoding="utf-8")
            results.append({"name": name, "command": command, "exit_code": code,
                            "log": log.name, "sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
            print(f"{name}: exit {code}", flush=True)
            if code and name == "install":
                break
    report = {"schema": "textlayout.installed-wheel-check.v1",
              "wheel": wheel.name, "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
              "platform": platform.platform(), "python": sys.version,
              "commands": results, "passed": len(results) == 6 and all(r["exit_code"] == 0 for r in results)}
    (out / "installed-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
