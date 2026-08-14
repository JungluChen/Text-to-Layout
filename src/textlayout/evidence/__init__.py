"""The trustworthy evidence contract and the canonical, content-addressed record.

``textlayout.evidence.contract`` holds the per-quantity honesty contract
(:class:`QuantityEvidence`, the confidence lattice, the ledger).
``textlayout.evidence.canonical`` holds the single source of truth that every
public artifact is derived from.

Importing names straight from ``textlayout.evidence`` keeps working.
"""

from __future__ import annotations

from textlayout.evidence.agreement import (
    AGREEMENT_SCHEMA,
    SolverAgreementMember,
    SolverAgreementRecord,
    SolverOutputDigest,
    convert_value,
    solver_family,
)
from textlayout.evidence.canonical import (
    CANONICAL_SCHEMA,
    CanonicalEvidence,
    ConvergenceMetrics,
    load_canonical,
    write_canonical,
)
from textlayout.evidence.contract import (
    LEDGER_SCHEMA,
    SOLVER_BACKED_STATUSES,
    VERIFIED_STATUSES,
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
    "AGREEMENT_SCHEMA",
    "CANONICAL_SCHEMA",
    "LEDGER_SCHEMA",
    "SOLVER_BACKED_STATUSES",
    "VERIFIED_STATUSES",
    "CanonicalEvidence",
    "ConfidenceClass",
    "ConvergenceMetrics",
    "EvidenceError",
    "EvidenceLedger",
    "EvidenceStatus",
    "QuantityEvidence",
    "SolverAgreementMember",
    "SolverAgreementRecord",
    "SolverOutputDigest",
    "compare_extracted_to_target",
    "confidence_of",
    "convert_value",
    "is_legal_transition",
    "load_canonical",
    "solver_family",
    "validate_transition",
    "write_canonical",
]
