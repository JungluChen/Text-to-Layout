"""Cross-artifact evidence consistency: one result, one status, one value.

Every showcase publishes the same claim in many places -- ``simulation.json``,
``workflow_trace.json``, ``report.md``, its own ``README.md``, the top-level
README table, ``index.json``. Each of those carried a hand-maintained status
string, so correcting one could not correct the rest. This module reads every
representation, normalises it, and reports disagreement.

It traverses **every** directory under ``examples/showcase/`` -- never a
hard-coded subset -- so a new showcase is covered the day it is added.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textlayout.evidence.canonical import CanonicalEvidence, load_canonical
from textlayout.evidence.contract import EvidenceStatus

#: Solver-level vocabulary. `<QUANTITY>_EXTRACTED` means only "the parser
#: returned a number" -- it is an *extraction outcome*, not an evidence status,
#: and it is compatible with more than one status.
_EXTRACTED_RE = re.compile(r"^[A-Z_]+_EXTRACTED$")
_INPUT_PREPARED_RE = re.compile(r"^[A-Z_]*INPUT_PREPARED$")

#: Derived from the enum, never hand-listed: a status added to the contract but
#: forgotten here would silently escape every cross-artifact consistency check.
_STATUS_TOKENS: tuple[str, ...] = tuple(status.value for status in EvidenceStatus)

#: Files whose `status` is a solver-level extraction outcome, not an evidence
#: status. They constrain the evidence status without equalling it.
SOLVER_LEVEL_SOURCES = frozenset({"openems_result.json", "extraction/capacitance_result.json"})

#: Which evidence statuses each extraction outcome permits downstream.
_OUTCOME_COMPATIBILITY: dict[str, frozenset[str]] = {
    "EXTRACTED": frozenset({"SIMULATION_EXECUTED", "PHYSICS_VERIFIED"}),
    "INPUT_PREPARED": frozenset(
        {"SIMULATION_INPUT_PREPARED", "ANALYTICAL_ONLY", "SKIPPED_SOLVER_ABSENT"}
    ),
    "SIMULATION_INVALID": frozenset({"SIMULATION_INVALID"}),
    "CONVERGENCE_FAILED": frozenset({"CONVERGENCE_FAILED"}),
    "FAILED": frozenset({"FAILED"}),
    "SKIPPED_SOLVER_ABSENT": frozenset({"SKIPPED_SOLVER_ABSENT"}),
}

#: Markers delimiting a generated region of an otherwise hand-written document.
#: Only text inside these markers carries an authoritative status.
GENERATED_BEGIN = "<!-- BEGIN GENERATED: {name} -->"
GENERATED_END = "<!-- END GENERATED: {name} -->"
EVIDENCE_BLOCK = "evidence-status"


def classify_outcome(raw: str) -> str:
    """Reduce a solver-level status string to an extraction-outcome class."""
    token = raw.strip().upper()
    if _EXTRACTED_RE.match(token):
        return "EXTRACTED"
    if _INPUT_PREPARED_RE.match(token):
        return "INPUT_PREPARED"
    return token


def compatible(outcome: str, status: str) -> bool:
    """Whether an evidence `status` is permitted by a solver `outcome`."""
    allowed = _OUTCOME_COMPATIBILITY.get(classify_outcome(outcome))
    return status in allowed if allowed else classify_outcome(outcome) == status


def generated_block(text: str, name: str = EVIDENCE_BLOCK) -> str | None:
    """Return the contents of a generated block, or None when it is absent."""
    begin = GENERATED_BEGIN.format(name=name)
    end = GENERATED_END.format(name=name)
    if begin not in text or end not in text:
        return None
    return text.split(begin, 1)[1].split(end, 1)[0]


@dataclass(frozen=True)
class Claim:
    """One artifact's assertion about one showcase."""

    source: str
    locator: str
    status: str | None = None
    extracted_value: float | None = None
    extracted_unit: str | None = None
    #: True when `status` is a solver-level extraction outcome rather than an
    #: evidence status, and must be checked for compatibility, not equality.
    solver_level: bool = False


@dataclass
class ShowcaseReport:
    showcase_id: str
    claims: list[Claim] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


#: The renderer's machine-readable status line. A generated block legitimately
#: *mentions* other status tokens in prose -- a superseded claim, a
#: fabrication-readiness note -- so the declared status must be read from its
#: marker. Scanning for "whichever token appears first" was only ever correct by
#: accident of how the token list happened to be ordered.
_DECLARED_STATUS_RE = re.compile(r"\*\*Status:\*\*\s*`([A-Z_]+)`")


def _first_status_token(text: str) -> str | None:
    """The status a document *declares*, not merely one it mentions.

    Prefer the explicit marker. Otherwise fall back to the earliest token by
    position -- a README showcase row leads with its status and closes with a
    fabrication-readiness note, so `PHYSICS_VERIFIED ... NOT_FABRICATION_READY`
    declares the former. Among tokens starting at the same offset the longest
    wins, so `CONVERGENCE_FAILED` is never mistaken for the `FAILED` inside it.
    """
    declared = _DECLARED_STATUS_RE.search(text)
    if declared and declared.group(1) in _STATUS_TOKENS:
        return declared.group(1)
    best: tuple[int, int, str] | None = None
    for token in _STATUS_TOKENS:
        index = text.find(token)
        if index == -1:
            continue
        candidate = (index, -len(token), token)
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) else None
    return None


def collect_claims(showcase_dir: Path, repo_root: Path) -> list[Claim]:
    """Read every representation of this showcase's headline claim."""
    claims: list[Claim] = []
    sid = showcase_dir.name

    for name in ("simulation.json", "simulation/simulation.json"):
        payload = _load_json(showcase_dir / name)
        if payload is None:
            continue
        claims.append(
            Claim(
                source=name,
                locator=f"{sid}/{name}#/status",
                status=str(payload.get("status", "")).strip().upper() or None,
                extracted_value=_numeric(payload.get("extracted_value")),
                extracted_unit=payload.get("extracted_unit"),
            )
        )
        # simulation.json embeds per-quantity QuantityEvidence records: a second
        # representation of the same claim, and a place drift has hidden before.
        for position, item in enumerate(payload.get("evidence") or []):
            if not isinstance(item, dict):
                continue
            claims.append(
                Claim(
                    source=f"{name}#/evidence[{position}]",
                    locator=f"{sid}/{name}#/evidence[{position}]/status",
                    status=str(item.get("status", "")).strip().upper() or None,
                    extracted_value=_numeric(item.get("extracted_value")),
                    extracted_unit=item.get("extracted_unit"),
                )
            )

    for name in sorted(SOLVER_LEVEL_SOURCES):
        payload = _load_json(showcase_dir / name)
        if payload is None:
            continue
        quantities = payload.get("extracted_quantities") or {}
        value = None
        if isinstance(quantities, dict):
            for key, raw in quantities.items():
                if key.endswith(("_ghz", "_pf", "_nh", "_ohm")) and "sample_frequency" not in key:
                    value = _numeric(raw)
                    if value is not None:
                        break
        claims.append(
            Claim(
                source=name,
                locator=f"{sid}/{name}#/status",
                status=str(payload.get("status", "")).strip().upper() or None,
                extracted_value=value,
                solver_level=True,
            )
        )

    trace = _load_json(showcase_dir / "workflow_trace.json")
    if trace is not None:
        claims.append(
            Claim(
                source="workflow_trace.json",
                locator=(
                    f"{sid}/workflow_trace.json#/canonical_evidence_status"
                    if "canonical_evidence_status" in trace
                    else f"{sid}/workflow_trace.json (no generated block)"
                ),
                status=_trace_status(trace),
            )
        )

    # Markdown: only the generated block is authoritative. A status word that
    # appears in prose (e.g. a sub-block note in the test-chip report) is not a
    # claim about the showcase's headline evidence.
    for markdown in ("report.md", "README.md"):
        path = showcase_dir / markdown
        if not path.is_file():
            continue
        block = generated_block(path.read_text(encoding="utf-8"))
        if block is None:
            claims.append(
                Claim(
                    source=markdown,
                    locator=f"{sid}/{markdown} (no generated block)",
                    status=None,
                )
            )
            continue
        token = _first_status_token(block)
        if token:
            claims.append(
                Claim(
                    source=markdown,
                    locator=f"{sid}/{markdown}#{EVIDENCE_BLOCK}",
                    status=token,
                    extracted_value=_markdown_value(block),
                )
            )

    index = _load_json(showcase_dir.parent / "index.json")
    if index is not None:
        for entry in index.get("examples", []):
            if entry.get("id") == sid:
                claims.append(
                    Claim(
                        source="index.json",
                        locator=f"showcase/index.json#/examples[{sid}]/evidence_status",
                        status=str(entry.get("evidence_status", "")).strip().upper() or None,
                    )
                )
                break

    readme = repo_root / "README.md"
    if readme.is_file():
        block = generated_block(readme.read_text(encoding="utf-8"), "showcase-table")
        if block is None:
            claims.append(
                Claim(source="README.md", locator="README.md (no generated block)", status=None)
            )
        else:
            for line in block.splitlines():
                if f"examples/showcase/{sid}/" in line and line.lstrip().startswith("|"):
                    token = _first_status_token(line)
                    if token:
                        claims.append(
                            Claim(
                                source="README.md",
                                locator="README.md#showcase-table",
                                status=token,
                                extracted_value=_markdown_value(line),
                            )
                        )
                    break
    return claims


_VALUE_RE = re.compile(r"extracted[^0-9`]{0,24}`?(-?\d+\.\d+)")


def _markdown_value(text: str) -> float | None:
    """Pull the published extracted value out of a generated Markdown block."""
    match = _VALUE_RE.search(text.lower())
    return float(match.group(1)) if match else None


def _trace_status(trace: dict[str, Any]) -> str | None:
    """Only the canonical stamp is authoritative.

    A trace's per-node summaries record what the workflow observed when it ran.
    They are audit history -- `run_reported_status` names the status that run
    reported -- and must never be read as a claim about current evidence.
    """
    stamped = trace.get("canonical_evidence_status")
    return str(stamped).strip().upper() if isinstance(stamped, str) else None


def _value_agrees(a: float, b: float) -> bool:
    """Serialization rule: agreement to 6 significant figures."""
    if a == b:
        return True
    scale = max(abs(a), abs(b))
    return scale > 0 and abs(a - b) / scale < 1e-6


def check_showcase(
    showcase_dir: Path, repo_root: Path, *, canonical: CanonicalEvidence | None = None
) -> ShowcaseReport:
    report = ShowcaseReport(showcase_id=showcase_dir.name)
    report.claims = collect_claims(showcase_dir, repo_root)

    for claim in report.claims:
        if claim.status is None and "no generated block" in claim.locator:
            report.problems.append(
                f"{claim.locator}: status section is hand-maintained; it cannot be "
                "regenerated from canonical evidence or checked for staleness"
            )

    evidence_claims = [c for c in report.claims if c.status and not c.solver_level]
    statuses = {c.status for c in evidence_claims}
    if len(statuses) > 1:
        detail = ", ".join(f"{c.source}={c.status}" for c in evidence_claims)
        report.problems.append(f"status disagreement across artifacts: {detail}")

    # A solver-level outcome constrains every evidence status derived from it,
    # whether or not a canonical record exists yet. This is what catches
    # "openems_result.json says SIMULATION_INVALID but simulation.json says
    # SIMULATION_EXECUTED".
    for solver_claim in (c for c in report.claims if c.solver_level and c.status):
        for evidence_claim in evidence_claims:
            if not compatible(solver_claim.status or "", evidence_claim.status or ""):
                report.problems.append(
                    f"{solver_claim.locator} records solver outcome "
                    f"{solver_claim.status}, which does not permit "
                    f"{evidence_claim.locator} = {evidence_claim.status}"
                )

    values = [(c.source, c.extracted_value) for c in report.claims if c.extracted_value is not None]
    for source, value in values[1:]:
        if not _value_agrees(values[0][1], value):
            report.problems.append(
                f"extracted-value disagreement: {values[0][0]}={values[0][1]!r} "
                f"vs {source}={value!r}"
            )

    if canonical is None:
        return report

    expected = canonical.status.value
    for claim in report.claims:
        if claim.status is None:
            continue
        if claim.solver_level:
            if not compatible(claim.status, expected):
                report.problems.append(
                    f"{claim.locator} records the solver outcome {claim.status}, which "
                    f"does not permit the canonical status {expected}"
                )
        elif claim.status != expected:
            report.problems.append(
                f"{claim.locator} says {claim.status} but canonical evidence says {expected}"
            )

        if claim.extracted_value is None:
            continue
        if canonical.extracted_value is None:
            report.problems.append(
                f"{claim.locator} publishes an extracted value {claim.extracted_value!r} "
                f"but canonical evidence is {expected} and extracted nothing"
            )
        elif not _value_agrees(claim.extracted_value, canonical.extracted_value):
            report.problems.append(
                f"{claim.locator} reports {claim.extracted_value!r} but canonical "
                f"evidence reports {canonical.extracted_value!r}"
            )

    report.problems.extend(
        f"canonical {canonical.evidence_id}: {problem}"
        for problem in canonical.verify_output_hashes(showcase_dir)
    )
    return report


def iter_showcases(repo_root: Path) -> list[Path]:
    root = repo_root / "examples" / "showcase"
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "simulation.json").is_file())


def canonical_path(showcase_dir: Path) -> Path:
    return showcase_dir / "evidence" / "canonical.json"


def audit(repo_root: Path) -> list[ShowcaseReport]:
    """Validate every showcase. Traverses the directory, never a fixed list."""
    reports: list[ShowcaseReport] = []
    for showcase in iter_showcases(repo_root):
        path = canonical_path(showcase)
        canonical = load_canonical(path) if path.is_file() else None
        report = check_showcase(showcase, repo_root, canonical=canonical)
        if canonical is None:
            report.problems.append(
                "no canonical evidence record (evidence/canonical.json); statuses are "
                "hand-maintained and cannot be cross-checked"
            )
        reports.append(report)
    return reports


def to_json(reports: list[ShowcaseReport]) -> dict[str, Any]:
    return {
        "schema": "textlayout.evidence-consistency-report.v1",
        "showcases_audited": len(reports),
        "showcases_with_problems": sum(1 for r in reports if not r.ok),
        "results": [
            {
                "showcase_id": r.showcase_id,
                "ok": r.ok,
                "problems": r.problems,
                "claims": [
                    {
                        "source": c.source,
                        "locator": c.locator,
                        "status": c.status,
                        "extracted_value": c.extracted_value,
                    }
                    for c in r.claims
                ],
            }
            for r in reports
        ],
    }
