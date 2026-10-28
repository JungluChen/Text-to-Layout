"""Bind supplied snapshots to one retained QEDA node_modules audit."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from textlayout.external.qeda_inventory import InventoryComparison, compare_inventories

AUDIT_ID = 'qeda-0.4.1-node-modules-2026-10-26'
AUDIT_SHA256 = '0d3354e18cb8aec1ac647fcfaed646273651c607d959be944b39121f86582002'


@dataclass(frozen=True)
class AuditedInventoryComparison:
    audit_id: str
    comparison: InventoryComparison


def compare_audited_inventory(expected: bytes, observed: bytes) -> AuditedInventoryComparison:
    """Require exact retained baseline bytes before comparing supplied records.

    The pin identifies a repository audit, not upstream publisher attestation.
    It covers node_modules only: no Node executable, root lock/package, capture
    freshness, installation readiness or execution claim. Neither input is read
    from disk here. Even semantically equivalent reformatted baseline bytes fail.
    """
    if len(expected) > 2 * 1024**2:
        raise ValueError('audited inventory exceeds byte limit')
    if hashlib.sha256(expected).hexdigest() != AUDIT_SHA256:
        raise ValueError('expected inventory does not match the retained QEDA audit')
    return AuditedInventoryComparison(AUDIT_ID, compare_inventories(expected, observed))
