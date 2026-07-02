#!/usr/bin/env python
"""One-command simulator bootstrap: JoSIM first, then PSCAN2, then WRspice.

Usage (or via ``make setup-simulators``)::

    python scripts/bootstrap_simulators.py [--detect-only] [--strict] [--tools-dir DIR]

Policy:

- JoSIM is the primary backend and the only one this script tries to install
  automatically (official MIT-licensed release artifact, else source build,
  else exact manual steps).
- PSCAN2 and WRspice are detected and documented; their absence never blocks
  JoSIM setup or the normal workflow.
- Nothing here fakes availability: the final table comes from
  ``scripts/check_simulators.py`` and every claim is re-verified by actually
  running the executables.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
from pathlib import Path

import check_simulators as checker
import install_josim
import install_pscan2
import install_wrspice


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tools-dir", default=None)
    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Only detect; never download, build, or print install walls of text.",
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    strict = args.strict or os.environ.get("TEXTLAYOUT_STRICT_SIMULATORS") == "1"
    tools_dir = Path(args.tools_dir) if args.tools_dir else checker.default_tools_dir()

    print("=" * 70)
    print("textlayout simulator bootstrap")
    print(f"  platform : {platform.platform()}")
    print(f"  machine  : {platform.machine()}")
    print(f"  python   : {platform.python_version()} ({sys.executable})")
    print(f"  tools dir: {tools_dir}")
    print(f"  strict   : {strict}")
    print("=" * 70)

    print("\n--- [1/3] JoSIM (primary) " + "-" * 42)
    josim = install_josim.ensure_josim(tools_dir, detect_only=args.detect_only)

    print("\n--- [2/3] PSCAN2 (optional) " + "-" * 40)
    install_pscan2.ensure_pscan2(tools_dir, detect_only=args.detect_only)

    print("\n--- [3/3] WRspice (optional) " + "-" * 39)
    install_wrspice.ensure_wrspice(tools_dir, detect_only=args.detect_only)

    print("\n--- summary " + "-" * 56)
    checker_args = ["--tools-dir", str(tools_dir)]
    if strict:
        checker_args.append("--strict")
    exit_code = checker.main(checker_args)

    print("\nNext commands:")
    print("  make check-simulators")
    print("  make demo-jpa")
    if not josim.available:
        print(
            "\nNote: JoSIM is not available; demos will still run and honestly "
            "report SKIPPED_SOLVER_ABSENT for circuit checks."
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
