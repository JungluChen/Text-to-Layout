"""Install and verify the open-source FastHenry 3.0.1 solver under WSL.

The upstream source predates GCC 10 and requires ``-fcommon``. This installer
keeps that compatibility flag in the build command; it does not vendor solver
source or treat installation as simulation evidence.
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://github.com/ediloren/FastHenry2.git"


def _wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive}/{tail}"


def _run(command: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def install(tools_dir: Path, *, detect_only: bool = False) -> int:
    source = tools_dir / "FastHenry2"
    executable = source / "bin" / "fasthenry"
    if executable.is_file() and executable.read_bytes()[:4] == b"\x7fELF":
        print(f"[ok] FastHenry ELF: {executable}")
        return 0
    if detect_only:
        print("[missing] FastHenry ELF; run this script without --detect-only")
        return 2
    if shutil.which("wsl") is None:
        print("[missing] WSL is required for the supported FastHenry build")
        return 2
    tools_dir.mkdir(parents=True, exist_ok=True)
    if not (source / ".git").is_dir():
        cloned = _run(["git", "clone", "--depth", "1", UPSTREAM, str(source)], timeout=300)
        if cloned.returncode != 0:
            print(cloned.stderr)
            return cloned.returncode
    source_wsl = _wsl_path(source)
    build = " && ".join(
        (
            f"cd {shlex.quote(source_wsl)}",
            "sed -i 's/\\r$//' config",
            "bash ./config x64",
            "make clean >/dev/null 2>&1 || true",
            "make fasthenry CFLAGS='-O -DFOUR -m64 -fcommon'",
            "file bin/fasthenry",
            "bin/fasthenry -h >/dev/null",
        )
    )
    completed = _run(["wsl", "bash", "-lc", build], timeout=900)
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr)
        return completed.returncode
    print(f"[ok] FastHenry 3.0.1 built and verified: {executable}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-dir", type=Path, default=ROOT / ".tools")
    parser.add_argument("--detect-only", action="store_true")
    args = parser.parse_args(argv)
    return install(args.tools_dir, detect_only=args.detect_only)


if __name__ == "__main__":
    raise SystemExit(main())
