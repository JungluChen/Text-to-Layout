"""Compatibility entry point for the retired ``text_to_gds.server`` path."""

from __future__ import annotations

import sys

from textlayout._legacy import server as _target

__textlayout_shim__ = True

if __name__ == "__main__":
    _target.main()
else:
    sys.modules[__name__] = _target
