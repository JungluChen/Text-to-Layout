"""Map raw :class:`SimulationResult` records onto the typed evidence contract.

This is the single place where a solver run becomes an evidence claim. The
mapping is deliberately conservative:

- ``input_files_prepared`` → ``SIMULATION_INPUT_PREPARED``
- ``skipped``              → ``SKIPPED_SOLVER_ABSENT``
- ``failed``               → ``FAILED``
- ``executed``             → compared against the target; ``PHYSICS_VERIFIED``
  only when the extracted value is within tolerance, else ``SIMULATION_EXECUTED``.

Anything unrecognised maps to ``FAILED`` — an unknown status is never promoted.
"""

from __future__ import annotations

from pathlib import Path

from textlayout.evidence import (
    EvidenceStatus,
    QuantityEvidence,
    compare_extracted_to_target,
)
from textlayout.simulation.models import SimulationResult

_PARSER = "textlayout.simulation.fastercap._parse_capacitance_matrix_pf"

_INPUT_KEYS = ("panel_file", "list_file", "manifest", "input_file", "input", "driver", "model")
_OUTPUT_KEYS = ("solver_stdout", "solver_stderr", "result", "touchstone", "zc_matrix")


def _existing_outputs(simulation: SimulationResult) -> list[str]:
    """Solver-owned output files that actually carry content.

    An empty stderr log is normal for a clean run and is not evidence, so it is
    excluded rather than allowed to trip the non-empty-output contract check.
    """
    outputs: list[str] = []
    for key in _OUTPUT_KEYS:
        name = simulation.artifacts.get(key)
        if name is None:
            continue
        path = Path(name)
        if path.is_file() and path.stat().st_size > 0:
            outputs.append(name)
    return outputs


def capacitance_evidence(
    simulation: SimulationResult,
    *,
    target_capacitance_pf: float | None,
    tolerance_percent: float = 5.0,
    analytical_value_pf: float | None = None,
    analytical_model: str | None = None,
) -> QuantityEvidence:
    """Build the capacitance evidence record for one simulation attempt."""
    input_files = [simulation.artifacts[k] for k in _INPUT_KEYS if k in simulation.artifacts]
    output_files = _existing_outputs(simulation)
    command = " ".join(simulation.command) if simulation.command else None
    notes = [simulation.reason, *simulation.warnings]

    if simulation.status == "executed":
        extracted = simulation.extracted_quantities.get("mutual_capacitance_pf")
        if not isinstance(extracted, (int, float)):
            return QuantityEvidence(
                quantity="capacitance",
                target_value=target_capacitance_pf,
                target_unit="pF",
                analytical_value=analytical_value_pf,
                analytical_model=analytical_model,
                tolerance_percent=tolerance_percent,
                status=EvidenceStatus.FAILED,
                solver=simulation.solver,
                command=command,
                input_files=input_files,
                output_files=output_files,
                parser=_PARSER,
                notes=[*notes, "Solver ran but no mutual capacitance could be extracted."],
            )
        if target_capacitance_pf is None:
            # Executed with no stated target: report the extraction, never
            # "verified" — there is nothing to verify against.
            return QuantityEvidence(
                quantity="capacitance",
                extracted_value=float(extracted),
                extracted_unit="pF",
                analytical_value=analytical_value_pf,
                analytical_model=analytical_model,
                tolerance_percent=tolerance_percent,
                status=EvidenceStatus.SIMULATION_EXECUTED,
                solver=simulation.solver,
                command=command,
                input_files=input_files,
                output_files=output_files,
                parser=_PARSER,
                notes=[*notes, "No target capacitance was stated; comparison skipped."],
            )
        return compare_extracted_to_target(
            quantity="capacitance",
            target_value=target_capacitance_pf,
            target_unit="pF",
            extracted_value=float(extracted),
            extracted_unit="pF",
            tolerance_percent=tolerance_percent,
            solver=simulation.solver,
            command=command or "",
            input_files=input_files,
            output_files=output_files,
            parser=_PARSER,
            analytical_value=analytical_value_pf,
            analytical_model=analytical_model,
            notes=notes,
        )

    status_map = {
        "input_files_prepared": EvidenceStatus.SIMULATION_INPUT_PREPARED,
        "skipped": EvidenceStatus.SKIPPED_SOLVER_ABSENT,
        "failed": EvidenceStatus.FAILED,
    }
    status = status_map.get(simulation.status, EvidenceStatus.FAILED)
    if simulation.status not in status_map:
        notes.append(f"Unrecognised simulation status {simulation.status!r} demoted to FAILED.")
    return QuantityEvidence(
        quantity="capacitance",
        target_value=target_capacitance_pf,
        target_unit="pF" if target_capacitance_pf is not None else None,
        analytical_value=analytical_value_pf,
        analytical_model=analytical_model,
        tolerance_percent=tolerance_percent,
        status=status,
        solver=simulation.solver,
        command=command,
        input_files=input_files,
        output_files=output_files,
        parser=None,
        notes=notes,
    )


def quantity_evidence(
    simulation: SimulationResult,
    *,
    quantity: str,
    extracted_key: str,
    unit: str,
    target_value: float | None,
    tolerance_percent: float,
    parser: str,
    analytical_value: float | None = None,
    analytical_model: str | None = None,
) -> QuantityEvidence:
    """Map any adapter result through the same structural evidence contract."""
    input_files = [simulation.artifacts[k] for k in _INPUT_KEYS if k in simulation.artifacts]
    output_files = _existing_outputs(simulation)
    command = " ".join(simulation.command) if simulation.command else None
    notes = [simulation.reason, *simulation.warnings]
    if simulation.status == "executed":
        extracted = simulation.extracted_quantities.get(extracted_key)
        if not isinstance(extracted, (int, float)) or not output_files:
            return QuantityEvidence(
                quantity=quantity,
                target_value=target_value,
                target_unit=unit if target_value is not None else None,
                analytical_value=analytical_value,
                analytical_model=analytical_model,
                tolerance_percent=tolerance_percent,
                status=EvidenceStatus.FAILED,
                solver=simulation.solver,
                command=command,
                input_files=input_files,
                output_files=output_files,
                parser=parser,
                notes=[*notes, f"Solver ran but {extracted_key} was not accepted."],
            )
        if target_value is None:
            return QuantityEvidence(
                quantity=quantity,
                extracted_value=float(extracted),
                extracted_unit=unit,
                analytical_value=analytical_value,
                analytical_model=analytical_model,
                tolerance_percent=tolerance_percent,
                status=EvidenceStatus.SIMULATION_EXECUTED,
                solver=simulation.solver,
                command=command,
                input_files=input_files,
                output_files=output_files,
                parser=parser,
                notes=[*notes, "No target was stated; comparison skipped."],
            )
        return compare_extracted_to_target(
            quantity=quantity,
            target_value=target_value,
            target_unit=unit,
            extracted_value=float(extracted),
            extracted_unit=unit,
            tolerance_percent=tolerance_percent,
            solver=simulation.solver,
            command=command or "",
            input_files=input_files,
            output_files=output_files,
            parser=parser,
            analytical_value=analytical_value,
            analytical_model=analytical_model,
            notes=notes,
        )
    if simulation.status == "planned":
        return QuantityEvidence(
            quantity=quantity,
            target_value=target_value,
            target_unit=unit if target_value is not None else None,
            analytical_value=analytical_value,
            analytical_model=analytical_model,
            tolerance_percent=tolerance_percent,
            status=EvidenceStatus.ANALYTICAL_ONLY,
            notes=notes,
        )
    status = {
        "input_files_prepared": EvidenceStatus.SIMULATION_INPUT_PREPARED,
        "skipped": EvidenceStatus.SKIPPED_SOLVER_ABSENT,
        "failed": EvidenceStatus.FAILED,
    }.get(simulation.status, EvidenceStatus.FAILED)
    return QuantityEvidence(
        quantity=quantity,
        target_value=target_value,
        target_unit=unit if target_value is not None else None,
        analytical_value=analytical_value,
        analytical_model=analytical_model,
        tolerance_percent=tolerance_percent,
        status=status,
        solver=simulation.solver,
        command=command,
        input_files=input_files,
        output_files=output_files,
        notes=notes,
    )
