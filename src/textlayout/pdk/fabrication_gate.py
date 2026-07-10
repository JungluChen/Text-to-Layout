"""Let DRC block a design, without letting it touch the physics.

``NOT_FABRICATION_READY`` has existed in the evidence vocabulary since the
canonical schema was written, enforced by the model and produced by nothing. A
status no code can emit is a promise, not a guarantee.

DRC is its natural producer, and the lattice already has the right shape for it.
A DRC result is not a competing *physics* claim -- a resonance can be
PHYSICS_VERIFIED to four digits while the layout violates a minimum spacing. The
two are orthogonal, which is exactly why ``NOT_FABRICATION_READY`` carries
``ConfidenceClass.NONE`` and why the gate *demotes* rather than replaces: the
extracted value survives, because it was never in question. What is withdrawn is
permission to tape the design out.

The demotion is a confidence-lowering transition, which the lattice always
permits. Nothing here can promote anything.
"""

from __future__ import annotations

from textlayout.evidence.canonical import ArtifactDependency, CanonicalEvidence, SupersededClaim
from textlayout.evidence.contract import EvidenceStatus, validate_transition
from textlayout.pdk.klayout_drc import DRCReport


def apply_fabrication_gate(
    evidence: CanonicalEvidence, report: DRCReport
) -> CanonicalEvidence:
    """Demote ``evidence`` to ``NOT_FABRICATION_READY`` when DRC blocks the design.

    Returns the record unchanged when the DRC run is signoff-ready. The physics
    claim is never strengthened by a clean DRC: a layout passing its design rules
    says nothing about whether its resonance was computed correctly.
    """
    blocking = report.blocking_reason()
    if blocking is None:
        return evidence
    if evidence.status is EvidenceStatus.NOT_FABRICATION_READY:
        return evidence

    # Always legal: confidence may be lost at any time. Asserted rather than
    # assumed, so a future vocabulary change cannot make this silently illegal.
    validate_transition(evidence.status, EvidenceStatus.NOT_FABRICATION_READY)

    payload = evidence.to_dict()
    payload.pop("confidence_class", None)
    payload["status"] = EvidenceStatus.NOT_FABRICATION_READY.value
    payload["blocking_reason"] = blocking
    payload["supersedes_evidence_id"] = evidence.evidence_id
    payload["superseded"] = SupersededClaim(
        evidence_id=evidence.evidence_id,
        status=evidence.status.value,
        extracted_value=evidence.extracted_value,
        extracted_unit=evidence.extracted_unit,
        why_withdrawn=(
            f"design rule check against {report.pdk_name} {report.pdk_version} blocks "
            f"fabrication: {blocking}. The extracted value is not disputed; the "
            "design may not be taped out."
        ),
    ).model_dump(mode="json")
    payload["warnings"] = [
        *evidence.warnings,
        f"DRC gate: {blocking}",
        f"DRC ran {sum(1 for check in report.checks if check.ran)} checks and skipped "
        f"{sum(1 for check in report.checks if not check.ran)}; rules not implemented: "
        f"{', '.join(report.unsupported_rules)}",
    ]
    payload["depends_on"] = [
        *(dependency.model_dump(mode="json") for dependency in evidence.depends_on),
        ArtifactDependency(
            role="drc_input_gds", artifact=report.top_cell, sha256=report.gds_sha256
        ).model_dump(mode="json"),
    ]
    # PHYSICS_VERIFIED's convergence and tolerance requirements do not apply to a
    # blocked design, but revalidating is what proves the demoted record is legal.
    return CanonicalEvidence.model_validate(payload)
