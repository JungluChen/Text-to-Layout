"""Summarize a real Touchstone file with scikit-rf."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("touchstone", type=Path)
    parser.add_argument("--out", type=Path, default=Path("sparameter_summary.json"))
    args = parser.parse_args()
    if not args.touchstone.is_file() or args.touchstone.stat().st_size == 0:
        print(json.dumps({"status": "skipped", "reason": "Non-empty Touchstone file required."}))
        return 2
    try:
        import skrf as rf
    except ImportError:
        print(json.dumps({"status": "skipped", "reason": "Install scikit-rf to post-process Touchstone data."}))
        return 2
    network = rf.Network(str(args.touchstone))
    payload = {
        "status": "executed",
        "source_touchstone": str(args.touchstone),
        "points": len(network.f),
        "frequency_start_hz": float(network.f[0]),
        "frequency_stop_hz": float(network.f[-1]),
        "s11_min_db": float(network.s_db[:, 0, 0].min()),
        "s21_max_db": float(network.s_db[:, 1, 0].max()),
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
