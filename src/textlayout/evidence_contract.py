"""Machine-checkable evidence contract for analytical and solver claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class EvidenceStatus(StrEnum):
    ANALYTICAL_ONLY = "ANALYTICAL_ONLY"
    SIMULATION_INPUT_PREPARED = "SIMULATION_INPUT_PREPARED"
    SIMULATION_EXECUTED = "SIMULATION_EXECUTED"
    PHYSICS_VERIFIED = "PHYSICS_VERIFIED"
    FAILED = "FAILED"
    SKIPPED_SOLVER_ABSENT = "SKIPPED_SOLVER_ABSENT"


@dataclass(frozen=True, slots=True)
class ExtractedValueEvidence:
    value: float
    source: str
    command: tuple[str, ...]
    input_files: tuple[str, ...]
    output_files: tuple[str, ...]
    parser_used: str
    timestamp: str
    units: str
    tolerance: dict[str, float | bool]

    @classmethod
    def create(
        cls,
        *,
        value: float,
        source: str,
        command: tuple[str, ...],
        input_files: tuple[str, ...],
        output_files: tuple[str, ...],
        parser_used: str,
        units: str,
        tolerance: dict[str, float | bool],
    ) -> ExtractedValueEvidence:
        if not command:
            raise ValueError("solver evidence requires the executed command")
        if not input_files or not all(Path(path).is_file() for path in input_files):
            raise ValueError("solver evidence requires existing input files")
        if not output_files or not all(
            Path(path).is_file() and Path(path).stat().st_size > 0 for path in output_files
        ):
            raise ValueError("solver evidence requires non-empty solver-owned output files")
        return cls(
            value=value,
            source=source,
            command=command,
            input_files=input_files,
            output_files=output_files,
            parser_used=parser_used,
            timestamp=datetime.now(timezone.utc).isoformat(),
            units=units,
            tolerance=tolerance,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
