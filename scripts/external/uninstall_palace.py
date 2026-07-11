"""Remove only Text-to-Layout's git-ignored Palace/Spack installation state."""

from __future__ import annotations

import argparse
import shutil

from _palace_common import INSTALL_RECORD, PALACE_ROOT, SPACK_ENV, TOOLS, run_wsl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purge-spack", action="store_true")
    args = parser.parse_args()
    INSTALL_RECORD.unlink(missing_ok=True)
    if PALACE_ROOT.is_dir():
        shutil.rmtree(PALACE_ROOT)
    if args.purge_spack:
        for path in (TOOLS / "spack", TOOLS / "spack-packages", TOOLS / "spack-config"):
            if path.is_dir() and TOOLS.resolve() in path.resolve().parents:
                shutil.rmtree(path)
        run_wsl('rm -rf "$HOME/.cache/textlayout-palace"', timeout=300)
    lock = SPACK_ENV / "spack.lock"
    lock.unlink(missing_ok=True)
    print("Palace installation state removed; downloaded source archives were retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
