"""Deprecated compatibility wrapper for the registry-driven tool checker."""

from __future__ import annotations

import sys
from pathlib import Path

EXTERNAL = Path(__file__).resolve().parent / "external"
if str(EXTERNAL) not in sys.path:
    sys.path.insert(0, str(EXTERNAL))

from check import main as registry_check  # noqa: E402


def main() -> int:
    print(
        "DEPRECATED: use `uv run python scripts/external/check.py`; "
        "registry.toml and lock.toml are the only tool-state sources.",
        file=sys.stderr,
    )
    return registry_check()


if __name__ == "__main__":
    raise SystemExit(main())
