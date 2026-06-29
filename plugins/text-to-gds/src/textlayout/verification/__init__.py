"""Verification: structured design-rule + geometry checks before export.

The IC-layout safety gate. Mirrors Text-to-CAD's "validate before you trust the
artifact" loop, specialised for design rules.
"""

from __future__ import annotations

from textlayout.verification.context import VerificationContext
from textlayout.verification.report import Check, CheckStatus, VerificationReport
from textlayout.verification.verifier import Verifier, default_verifier

__all__ = [
    "Check",
    "CheckStatus",
    "VerificationContext",
    "VerificationReport",
    "Verifier",
    "default_verifier",
]
