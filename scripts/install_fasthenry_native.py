"""Build a pinned FastHenry on macOS/Linux; keep source, logs and identity locally.

Usage: python scripts/install_fasthenry_native.py [--rebuild]
Requires git, make and clang (macOS Command Line Tools). No administrator access.
Windows users should use install_fasthenry.py for the existing WSL route.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://github.com/ediloren/FastHenry2.git"
REVISION = "363e43ed57ad3b9affa11cba5a86624fad0edaa9"
FLAGS = ("-O -DFOUR -fcommon -std=gnu89 -Wno-implicit-function-declaration "
         "-Wno-int-conversion -Wno-return-mismatch")


def install(tools_dir: Path, rebuild: bool = False) -> Path:
    if platform.system() not in {"Darwin", "Linux"}:
        raise RuntimeError("Use scripts/install_fasthenry.py for Windows/WSL")
    for tool in ("git", "make", "clang", "bash"):
        if not shutil.which(tool):
            raise RuntimeError(f"Missing {tool}; install the native development tools first")
    tools_dir = tools_dir.resolve()
    tools_dir.mkdir(parents=True, exist_ok=True)
    source = tools_dir / "FastHenry2"
    log = tools_dir / "fasthenry-native-build.log"
    commands: list[list[str]] = []

    def run(command: list[str], cwd: Path) -> str:
        commands.append(command)
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=900)
        with log.open("a") as stream:
            stream.write(json.dumps(command) + "\n" + result.stdout + result.stderr + "\n")
        if result.returncode:
            raise RuntimeError(f"Command failed ({result.returncode}); see {log}")
        return result.stdout + result.stderr

    if not source.exists():
        run(["git", "clone", UPSTREAM, str(source)], tools_dir)
        run(["git", "checkout", "--detach", REVISION], source)
    revision = run(["git", "rev-parse", "HEAD"], source).strip()
    if revision != REVISION:
        raise RuntimeError(f"Source revision differs from {REVISION}; choose a fresh --tools-dir")
    executable = source / "bin" / "fasthenry"
    if rebuild or not executable.is_file():
        run(["bash", "./config", "default"], source)
        if rebuild:
            run(["make", "clean"], source)
        run(["make", "fasthenry", "CC=clang", f"CFLAGS={FLAGS}"], source)
    help_text = run([str(executable), "-h"], source)
    if "FastHenry Version 3.0.1" not in help_text:
        raise RuntimeError("Executable did not identify itself as FastHenry 3.0.1")
    manifest = dict(upstream=UPSTREAM, revision=revision, executable=str(executable),
                    sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                    platform=platform.platform(), compiler=run(["clang", "--version"], source),
                    flags=FLAGS, commands=commands, log=str(log),
                    status="INSTALLATION_VERIFIED", simulation_executed=False,
                    physics_scope="normal-metal quasi-static; no kinetic inductance")
    (tools_dir / "fasthenry-native.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return executable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-dir", type=Path, default=ROOT / ".tools")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    print(install(args.tools_dir, args.rebuild))
