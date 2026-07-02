#!/usr/bin/env python
"""Detect (and document) PSCAN2 — an optional circuit-simulation backend.

Detection order: ``TEXTLAYOUT_PSCAN2`` → ``import pscan2`` → conda/mamba
environment hint. PSCAN2 (http://pscan2sim.org/) does not have a
reliably-scriptable installation path that this project can verify, so this
script never attempts a blind install and never fakes availability: when
PSCAN2 is absent the recorded status is ``manual_install_required`` and the
normal workflow (and JoSIM setup) continues unaffected.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import check_simulators as checker


def _print_manual_steps() -> None:
    conda = shutil.which("conda") or shutil.which("mamba")
    print(
        "\n[pscan2] manual installation is required:\n"
        "  1. Follow the official instructions at http://pscan2sim.org/\n"
        "     (PSCAN2 is typically installed into a conda environment).\n"
    )
    if conda:
        print(
            f"  conda detected at {conda}. Once PSCAN2 is installed in an\n"
            "  environment, either run textlayout from that environment or set:\n"
            "    TEXTLAYOUT_PSCAN2=<path to the environment's python>\n"
        )
    else:
        print(
            "  conda/mamba was not found. Install Miniconda/Miniforge first if\n"
            "  you want the conda-based PSCAN2 route.\n"
        )
    print("  Verification: python scripts/check_simulators.py\n")


def ensure_pscan2(tools_dir: Path, *, detect_only: bool = False) -> checker.Detection:
    detection = checker.detect_pscan2(tools_dir)
    if detection.available:
        checker.write_manifest_entry(
            tools_dir,
            "pscan2",
            {
                "status": checker.STATUS_READY,
                "path": detection.path,
                "method": detection.method,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )
        print(f"[pscan2] ready ({detection.method}): {detection.path}")
        return detection
    if not detect_only:
        _print_manual_steps()
    checker.write_manifest_entry(
        tools_dir,
        "pscan2",
        {
            "status": checker.STATUS_MANUAL,
            "reason": "no scriptable installation path is documented; see docs/simulators/install.md",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )
    print("[pscan2] not available; status recorded as manual_install_required (optional backend)")
    return detection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tools-dir", default=None)
    parser.add_argument("--detect-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    strict = args.strict or os.environ.get("TEXTLAYOUT_STRICT_SIMULATORS") == "1"
    tools_dir = Path(args.tools_dir) if args.tools_dir else checker.default_tools_dir()
    detection = ensure_pscan2(tools_dir, detect_only=args.detect_only)
    if strict and not detection.available:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
