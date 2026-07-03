"""Suite-wide fixtures for the textlayout tests.

The developer machine may have a real (WSL) FasterCap build under ``.tools``.
Tests were written against the CI baseline where no capacitance solver exists,
so by default the suite pins ``TEXTLAYOUT_FASTERCAP`` to a nonexistent path —
discovery then honestly reports "absent". Tests that want a solver (fake or
real) override the variable or pass an explicit executable, which always wins.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _fastercap_absent_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "TEXTLAYOUT_FASTERCAP", "textlayout-tests-no-fastercap-by-default"
    )
