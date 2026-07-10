"""The trustworthy evidence contract and the canonical, content-addressed record.

``textlayout.evidence.contract`` holds the per-quantity honesty contract
(:class:`QuantityEvidence`, the confidence lattice, the ledger).
``textlayout.evidence.canonical`` holds the single source of truth that every
public artifact is derived from.

Importing names straight from ``textlayout.evidence`` keeps working.
"""

from __future__ import annotations

from textlayout.evidence.contract import (
    LEDGER_SCHEMA,
    ConfidenceClass,
    EvidenceError,
    EvidenceLedger,
    EvidenceStatus,
    QuantityEvidence,
    compare_extracted_to_target,
    confidence_of,
    is_legal_transition,
    validate_transition,
)

__all__ = [
    "LEDGER_SCHEMA",
    "ConfidenceClass",
    "EvidenceError",
    "EvidenceLedger",
    "EvidenceStatus",
    "QuantityEvidence",
    "compare_extracted_to_target",
    "confidence_of",
    "is_legal_transition",
    "validate_transition",
]
