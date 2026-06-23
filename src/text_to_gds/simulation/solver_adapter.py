from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SolverResult:
    status: str
    reason: str
    solver: str
    output_path: Path | None
    parsed_data: dict[str, Any] | None
    execution_time_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "solver": self.solver,
            "output_path": str(self.output_path) if self.output_path is not None else None,
            "parsed_data": self.parsed_data,
            "execution_time_s": self.execution_time_s,
        }


class SolverAdapter(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def is_available(self) -> bool: ...

    @abc.abstractmethod
    def execute(
        self,
        input_data: dict[str, Any],
        *,
        output_dir: Path | None = None,
    ) -> SolverResult: ...


@dataclass
class BaseSolverAdapter(SolverAdapter):
    solver_name: str
    executable: str

    @property
    def name(self) -> str:
        return self.solver_name

    @abc.abstractmethod
    def is_available(self) -> bool: ...

    @abc.abstractmethod
    def _generate_input(
        self,
        input_data: dict[str, Any],
        *,
        output_dir: Path,
    ) -> Path: ...

    @abc.abstractmethod
    def _run_solver(self, input_path: Path) -> None: ...

    @abc.abstractmethod
    def _parse_output(self, output_path: Path) -> dict[str, Any]: ...

    @abc.abstractmethod
    def _validate_output(self, parsed: dict[str, Any]) -> bool: ...

    def execute(
        self,
        input_data: dict[str, Any],
        *,
        output_dir: Path | None = None,
    ) -> SolverResult:
        start = time.monotonic()
        if not self.is_available():
            return SolverResult(
                status="skipped",
                reason=f"{self.solver_name} is not installed",
                solver=self.solver_name,
                output_path=None,
                parsed_data=None,
                execution_time_s=0.0,
            )

        work_dir = output_dir or Path.cwd() / "workspace" / "artifacts"
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            input_path = self._generate_input(input_data, output_dir=work_dir)
            self._run_solver(input_path)
            parsed = self._parse_output(input_path)
            if not self._validate_output(parsed):
                return SolverResult(
                    status="failed",
                    reason="output validation failed",
                    solver=self.solver_name,
                    output_path=input_path,
                    parsed_data=parsed,
                    execution_time_s=time.monotonic() - start,
                )
            return SolverResult(
                status="success",
                reason="completed",
                solver=self.solver_name,
                output_path=input_path,
                parsed_data=parsed,
                execution_time_s=time.monotonic() - start,
            )
        except Exception as exc:
            return SolverResult(
                status="failed",
                reason=str(exc),
                solver=self.solver_name,
                output_path=None,
                parsed_data=None,
                execution_time_s=time.monotonic() - start,
            )
