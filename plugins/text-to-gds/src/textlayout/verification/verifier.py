"""The Verifier: runs a configurable set of checks and aggregates a report."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from textlayout.verification.checks import DEFAULT_CHECKS
from textlayout.verification.context import VerificationContext
from textlayout.verification.report import Check, VerificationReport

CheckFn = Callable[[VerificationContext], Check | None]


class Verifier:
    """Runs an ordered list of check functions against a context.

    Checks are injected, so a PDK or a stricter profile can supply its own set
    without modifying this class (Open/Closed).
    """

    def __init__(self, checks: Sequence[CheckFn] | None = None) -> None:
        self._checks: tuple[CheckFn, ...] = tuple(checks) if checks is not None else DEFAULT_CHECKS

    def verify(self, ctx: VerificationContext) -> VerificationReport:
        results: list[Check] = []
        for check in self._checks:
            outcome = check(ctx)
            if outcome is not None:
                results.append(outcome)
        return VerificationReport.from_checks(ctx.spec.component, results)


def default_verifier() -> Verifier:
    return Verifier()
