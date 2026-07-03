"""Subprocess fixture that emits controllable FasterCap-style output."""

from __future__ import annotations

import os
import sys


mode = os.environ.get("FAKE_FASTERCAP_MODE", "matrix")
if "-bv" in sys.argv or "-v" in sys.argv:
    print("FasterCap version fake-test-1.0")
    raise SystemExit(0)
if mode == "nonzero":
    print("fake FasterCap execution failed", file=sys.stderr)
    raise SystemExit(1)
if mode == "malformed":
    print("not a capacitance matrix")
    print("fake FasterCap malformed-output diagnostic", file=sys.stderr)
    raise SystemExit(0)

mutual_pf = float(os.environ.get("FAKE_FASTERCAP_MUTUAL_PF", "0.600"))
diagonal_pf = mutual_pf + 0.300
print("CAPACITANCE MATRIX, picofarads")
print(f"1 P1 {diagonal_pf:.12g} {-mutual_pf:.12g}")
print(f"2 P2 {-mutual_pf:.12g} {diagonal_pf:.12g}")
print("fake FasterCap completed", file=sys.stderr)
