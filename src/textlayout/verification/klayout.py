"""KLayout external-executable boundary for DRC/LVS runsets."""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KLayoutCapability:
    executable: str | None
    integration_mode: str = "process-isolated runset and report file exchange"

    @property
    def available(self) -> bool:
        return self.executable is not None


def detect_klayout(explicit: str | None = None) -> KLayoutCapability:
    executable = explicit if explicit else shutil.which("klayout") or shutil.which("klayout.exe")
    return KLayoutCapability(executable=executable)
