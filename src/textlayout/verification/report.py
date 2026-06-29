"""Verification result value objects.

Models the structured report an AI tool-caller consumes::

    {
      "status": "pass",
      "component": "IDC",
      "checks": [{"name": "minimum_gap", "status": "pass", "value_um": 2, "limit_um": 2}],
      "warnings": [],
      "errors": []
    }

Design principle borrowed from Text-to-CAD: *report only checks that actually
ran*. A check always carries its measured value and the limit it was tested
against, so the report is auditable rather than a bare boolean.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class Check:
    """A single verification check result."""

    name: str
    status: CheckStatus
    message: str = ""
    value: float | None = None
    limit: float | None = None
    unit: str = "um"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name, "status": self.status.value}
        if self.value is not None:
            out[f"value_{self.unit}"] = _round(self.value)
        if self.limit is not None:
            out[f"limit_{self.unit}"] = _round(self.limit)
        if self.message:
            out["message"] = self.message
        return out


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Aggregated verification result for one component."""

    component: str
    checks: tuple[Check, ...] = field(default_factory=tuple)

    @property
    def status(self) -> str:
        return "fail" if any(c.status is CheckStatus.FAIL for c in self.checks) else "pass"

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def errors(self) -> list[str]:
        return [c.message or c.name for c in self.checks if c.status is CheckStatus.FAIL]

    @property
    def warnings(self) -> list[str]:
        return [c.message or c.name for c in self.checks if c.status is CheckStatus.WARN]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "component": self.component,
            "checks": [c.to_dict() for c in self.checks],
            "warnings": self.warnings,
            "errors": self.errors,
        }

    @classmethod
    def from_checks(cls, component: str, checks: Sequence[Check]) -> VerificationReport:
        return cls(component=component, checks=tuple(checks))


def _round(value: float) -> float:
    return round(value, 4) + 0.0
