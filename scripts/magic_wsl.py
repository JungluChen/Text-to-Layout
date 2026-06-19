#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAGIC_ROOT = PROJECT_ROOT / ".tools" / "magic-wsl-root"
MAGIC_LAUNCHER = MAGIC_ROOT / "usr" / "bin" / "magic"
MAGIC_DNULL = MAGIC_ROOT / "usr" / "lib" / "x86_64-linux-gnu" / "magic" / "tcl" / "magicdnull"
MAGIC_LIB = MAGIC_ROOT / "usr" / "lib" / "x86_64-linux-gnu"
MAGIC_CAD_ROOT = MAGIC_ROOT / "usr" / "lib" / "x86_64-linux-gnu"
MAGIC_TCL_DIR = MAGIC_CAD_ROOT / "magic" / "tcl"
TCL_LIBRARY = MAGIC_ROOT / "usr" / "share" / "tcltk" / "tcl8.6"


def _to_wsl_path(path: str | Path) -> str:
    value = str(path)
    normalized = value.replace("\\", "/")
    if len(normalized) >= 3 and normalized[1:3] == ":/":
        drive = normalized[0].lower()
        return f"/mnt/{drive}/{normalized[3:]}"
    return normalized


def _translate_windows_paths(text: str) -> str:
    pattern = re.compile(r"([A-Za-z]):/([^\"\s]+)")

    def replace(match: re.Match[str]) -> str:
        drive = match.group(1).lower()
        suffix = match.group(2)
        return f"/mnt/{drive}/{suffix}"

    return pattern.sub(replace, text)


def _translate_script(path: Path) -> Path:
    text = path.read_text(encoding="utf-8")
    translated = _translate_windows_paths(text)
    translated_path = path.with_suffix(path.suffix + ".wsl.tcl")
    translated_path.write_text(translated, encoding="utf-8", newline="\n")
    return translated_path


def _localized_magic_tcl() -> Path:
    source_path = MAGIC_TCL_DIR / "magic.tcl"
    localized_path = MAGIC_TCL_DIR / "magic-local.tcl"
    source_text = source_path.read_text(encoding="utf-8")
    localized_text = source_text.replace(
        "/usr/lib/x86_64-linux-gnu/magic",
        _to_wsl_path(MAGIC_CAD_ROOT / "magic"),
    )
    localized_path.write_text(localized_text, encoding="utf-8", newline="\n")
    return localized_path


def _bootstrap_script(script_path: Path) -> Path:
    bootstrap_path = script_path.with_suffix(script_path.suffix + ".bootstrap.tcl")
    bootstrap = "\n".join(
        [
            "set argc 3",
            f'set argv [list -dnull -noconsole {_to_wsl_path(script_path)}]',
            f'source "{_to_wsl_path(_localized_magic_tcl())}"',
            "",
        ]
    )
    bootstrap_path.write_text(bootstrap, encoding="utf-8", newline="\n")
    return bootstrap_path


def main() -> int:
    if not MAGIC_DNULL.exists() or not MAGIC_LAUNCHER.exists():
        print(f"Magic WSL executable not found under: {MAGIC_ROOT}", file=sys.stderr)
        return 127

    script_path: Path | None = None
    for arg in sys.argv[1:]:
        if arg in {"-dnull", "-noconsole"}:
            continue
        candidate = Path(arg)
        if candidate.suffix.lower() == ".tcl" and candidate.exists():
            script_path = _translate_script(candidate.resolve())

    if script_path is None:
        print("Magic WSL wrapper expected a TCL script argument.", file=sys.stderr)
        return 2

    bootstrap_path = _bootstrap_script(script_path)
    command = [
        "wsl",
        "-e",
        "sh",
        "-lc",
        " ".join(
            [
                f'LD_LIBRARY_PATH="{_to_wsl_path(MAGIC_LIB)}"',
                f'TCL_LIBRARY="{_to_wsl_path(TCL_LIBRARY)}"',
                f'CAD_ROOT="{_to_wsl_path(MAGIC_CAD_ROOT)}"',
                f'"{_to_wsl_path(MAGIC_DNULL)}"',
                f'< "{_to_wsl_path(bootstrap_path)}"',
            ]
        ),
    ]
    completed = subprocess.run(command, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
