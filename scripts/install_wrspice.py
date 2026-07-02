#!/usr/bin/env python
"""Detect (and document) WRspice — an optional circuit-simulation backend.

Detection order: ``TEXTLAYOUT_WRSPICE`` → ``.tools/wrspice/bin/wrspice`` →
``.tools/wrspice/bin/wrspice64`` → PATH ``wrspice``/``wrspice64``.

WRspice is part of Whiteley Research's XicTools. This script deliberately
does **not** download binaries: the official distribution channel is
http://wrcad.com/xictools/ and redistribution/mirroring rules are not
something this project should assume (see docs/simulators/licenses.md).
When absent, the status is ``manual_install_required``; the normal workflow
and JoSIM setup continue unaffected.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from pathlib import Path

import check_simulators as checker


def _print_manual_steps(tools_dir: Path) -> None:
    exe = "wrspice.exe" if platform.system() == "Windows" else "wrspice"
    print(
        "\n[wrspice] manual installation is required:\n"
        "  1. Download WRspice for your platform from http://wrcad.com/xictools/\n"
        "     (or build from https://github.com/wrcad/xictools).\n"
        f"  2. Either place the executable at {tools_dir / 'wrspice' / 'bin' / exe}\n"
        "     or add it to PATH, or set TEXTLAYOUT_WRSPICE=<path to wrspice>.\n"
        "  3. Verify: python scripts/check_simulators.py\n"
    )


def ensure_wrspice(tools_dir: Path, *, detect_only: bool = False) -> checker.Detection:
    detection = checker.detect_wrspice(tools_dir)
    if detection.available:
        checker.write_manifest_entry(
            tools_dir,
            "wrspice",
            {
                "status": checker.STATUS_READY,
                "path": detection.path,
                "method": detection.method,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )
        print(f"[wrspice] ready ({detection.method}): {detection.path}")
        return detection
    if not detect_only:
        _print_manual_steps(tools_dir)
    checker.write_manifest_entry(
        tools_dir,
        "wrspice",
        {
            "status": checker.STATUS_MANUAL,
            "reason": "binaries are distributed by wrcad.com; automatic download is not attempted",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )
    print("[wrspice] not available; status recorded as manual_install_required (optional backend)")
    return detection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tools-dir", default=None)
    parser.add_argument("--detect-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    strict = args.strict or os.environ.get("TEXTLAYOUT_STRICT_SIMULATORS") == "1"
    tools_dir = Path(args.tools_dir) if args.tools_dir else checker.default_tools_dir()
    detection = ensure_wrspice(tools_dir, detect_only=args.detect_only)
    if strict and not detection.available:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
