"""Solver-evidence provenance records.

Every plotted curve or reported solver value must carry full provenance so a
reader can audit exactly which solver produced it, from which inputs, and
whether it actually ran. The honesty rule is enforced here: a record cannot
claim ``EXECUTED`` unless a real, non-empty output file exists on disk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATUS = {"EXECUTED", "PREPARED", "SKIPPED", "FAILED", "UNSUPPORTED"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exists_nonempty(path: str | Path | None) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.exists() and p.stat().st_size > 0


def solver_evidence(
    *,
    quantity: str,
    source_device: str,
    source_sidecar: str | Path | None,
    solver_name: str,
    solver_status: str,
    input_file: str | Path | None = None,
    output_file: str | Path | None = None,
    frequency_range_ghz: tuple[float, float] | list[float] | None = None,
    timestamp: str | None = None,
    value: Any = None,
    unit: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Build one provenance record for a single plotted/reported quantity."""
    status = solver_status.upper()
    if status not in VALID_STATUS:
        raise ValueError(f"solver_status must be one of {sorted(VALID_STATUS)}, got {solver_status!r}")
    out_exists = _exists_nonempty(output_file)
    # Honesty gate: never claim EXECUTED without a real output artifact.
    if status == "EXECUTED" and not out_exists:
        notes = (f"{notes}; " if notes else "") + "EXECUTED downgraded to FAILED: output_file missing/empty"
        status = "FAILED"
        value = None
    return {
        "quantity": quantity,
        "source_device": source_device,
        "source_sidecar": str(source_sidecar) if source_sidecar else None,
        "solver_name": solver_name,
        "solver_status": status,
        "input_file": str(input_file) if input_file else None,
        "output_file": str(output_file) if output_file else None,
        "output_file_exists": out_exists,
        "frequency_range_ghz": list(frequency_range_ghz) if frequency_range_ghz else None,
        "timestamp": timestamp or now_iso(),
        "value": value,
        "unit": unit,
        "notes": notes,
    }


def evidence_bundle(
    *,
    device: str,
    source_sidecar: str | Path | None,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble per-quantity records plus a summary of what is skipped."""
    skipped = [
        {"quantity": it["quantity"], "solver_name": it["solver_name"], "notes": it.get("notes")}
        for it in items
        if it["solver_status"] in {"SKIPPED", "FAILED", "UNSUPPORTED"}
    ]
    executed = [it["quantity"] for it in items if it["solver_status"] == "EXECUTED"]
    return {
        "schema": "text-to-gds.solver-evidence.v1",
        "device": device,
        "source_sidecar": str(source_sidecar) if source_sidecar else None,
        "generated": now_iso(),
        "executed_quantities": executed,
        "skipped_quantities": skipped,
        "evidence": items,
    }
