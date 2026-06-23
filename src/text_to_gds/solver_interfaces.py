from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from text_to_gds.openems_runner import run_openems
from text_to_gds.parasitics import export_fastcap, export_fasthenry

SolverStatus = Literal["executed", "skipped", "failed", "prepared"]


class SolverLifecycleResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    solver: str
    status: SolverStatus
    reason: str | None = None
    input_file: str | None = None
    output_file: str | None = None
    report_path: str | None = None
    parsed: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)


class BaseSolver(ABC):
    """Lifecycle interface for real solver handoff.

    Subclasses may prepare decks without a binary, but ``run`` must return
    ``status="skipped"`` when the executable is unavailable and must never
    synthesize solver outputs.
    """

    name: str

    @abstractmethod
    def prepare(self) -> SolverLifecycleResult: ...

    @abstractmethod
    def run(self) -> SolverLifecycleResult: ...

    @abstractmethod
    def parse(self) -> SolverLifecycleResult: ...

    @abstractmethod
    def validate(self) -> SolverLifecycleResult: ...

    def execute(self) -> dict[str, Any]:
        prepared = self.prepare()
        if prepared.status == "failed":
            return prepared.model_dump(mode="json")
        ran = self.run()
        if ran.status != "executed":
            return ran.model_dump(mode="json")
        parsed = self.parse()
        if parsed.status != "executed":
            return parsed.model_dump(mode="json")
        return self.validate().model_dump(mode="json")


class FastCapSolver(BaseSolver):
    name = "FastCap"

    def __init__(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar_path: str | Path | None = None,
        process_path: str | Path | None = None,
    ) -> None:
        self.gds_path = Path(gds_path)
        self.output_stem = Path(output_stem)
        self.sidecar_path = sidecar_path
        self.process_path = process_path
        self.report_path = self.output_stem.with_suffix(".fastcap.json")
        self.lst_path = self.output_stem.with_suffix(".lst")

    def prepare(self) -> SolverLifecycleResult:
        result = export_fastcap(
            self.gds_path,
            lst_path=self.lst_path,
            report_path=self.report_path,
            sidecar_path=self.sidecar_path,
            process_path=self.process_path,
            run=False,
        )
        return SolverLifecycleResult(
            solver=self.name,
            status="prepared",
            input_file=result["deck"]["lst_path"],
            report_path=str(self.report_path),
        )

    def run(self) -> SolverLifecycleResult:
        result = export_fastcap(
            self.gds_path,
            lst_path=self.lst_path,
            report_path=self.report_path,
            sidecar_path=self.sidecar_path,
            process_path=self.process_path,
            run=True,
        )
        status = _normalize_status(result.get("status"))
        return SolverLifecycleResult(
            solver=self.name,
            status=status,
            reason=_reason(result),
            input_file=result.get("deck", {}).get("lst_path"),
            output_file=result.get("report_path"),
            report_path=result.get("report_path"),
            parsed={"capacitance_matrix_pf": result.get("capacitance_matrix_pf")},
        )

    def parse(self) -> SolverLifecycleResult:
        return _parse_report(self.name, self.report_path, "capacitance_matrix_pf")

    def validate(self) -> SolverLifecycleResult:
        parsed = self.parse()
        matrix = parsed.parsed.get("capacitance_matrix_pf")
        ok = isinstance(matrix, list) and bool(matrix)
        return parsed.model_copy(
            update={
                "status": "executed" if ok else "failed",
                "reason": None if ok else "FastCap produced no capacitance matrix",
                "validation": {"has_capacitance_matrix": ok},
            }
        )


class FastHenrySolver(BaseSolver):
    name = "FastHenry"

    def __init__(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar_path: str | Path | None = None,
        process_path: str | Path | None = None,
    ) -> None:
        self.gds_path = Path(gds_path)
        self.output_stem = Path(output_stem)
        self.sidecar_path = sidecar_path
        self.process_path = process_path
        self.report_path = self.output_stem.with_suffix(".fasthenry.json")
        self.inp_path = self.output_stem.with_suffix(".inp")

    def prepare(self) -> SolverLifecycleResult:
        result = export_fasthenry(
            self.gds_path,
            inp_path=self.inp_path,
            report_path=self.report_path,
            sidecar_path=self.sidecar_path,
            process_path=self.process_path,
            run=False,
        )
        return SolverLifecycleResult(
            solver=self.name,
            status="prepared",
            input_file=result["deck"]["inp_path"],
            report_path=str(self.report_path),
        )

    def run(self) -> SolverLifecycleResult:
        result = export_fasthenry(
            self.gds_path,
            inp_path=self.inp_path,
            report_path=self.report_path,
            sidecar_path=self.sidecar_path,
            process_path=self.process_path,
            run=True,
        )
        status = _normalize_status(result.get("status"))
        return SolverLifecycleResult(
            solver=self.name,
            status=status,
            reason=_reason(result),
            input_file=result.get("deck", {}).get("inp_path"),
            output_file=result.get("report_path"),
            report_path=result.get("report_path"),
            parsed={"inductance_nh": result.get("inductance_nh")},
        )

    def parse(self) -> SolverLifecycleResult:
        return _parse_report(self.name, self.report_path, "inductance_nh")

    def validate(self) -> SolverLifecycleResult:
        parsed = self.parse()
        ok = parsed.parsed.get("inductance_nh") is not None
        return parsed.model_copy(
            update={
                "status": "executed" if ok else "failed",
                "reason": None if ok else "FastHenry produced no inductance matrix/value",
                "validation": {"has_inductance": ok},
            }
        )


class OpenEMSSolver(BaseSolver):
    name = "openEMS"

    def __init__(
        self,
        extraction_path: str | Path,
        *,
        output_stem: str | Path,
        openems_executable: str = "openEMS",
    ) -> None:
        self.extraction_path = Path(extraction_path)
        self.output_stem = Path(output_stem)
        self.sim_dir = self.output_stem.parent / f"{self.output_stem.name}.openems"
        self.report_path = self.output_stem.with_suffix(".openems.json")
        self.openems_executable = openems_executable

    def prepare(self) -> SolverLifecycleResult:
        if not self.extraction_path.is_file():
            return SolverLifecycleResult(
                solver=self.name,
                status="failed",
                reason=f"extraction file not found: {self.extraction_path}",
            )
        self.sim_dir.mkdir(parents=True, exist_ok=True)
        return SolverLifecycleResult(
            solver=self.name,
            status="prepared",
            input_file=str(self.extraction_path),
            report_path=str(self.report_path),
        )

    def run(self) -> SolverLifecycleResult:
        result = run_openems(
            self.extraction_path,
            sim_dir=self.sim_dir,
            report_path=self.report_path,
            openems_executable=self.openems_executable,
        )
        status = _normalize_status(result.get("status"))
        return SolverLifecycleResult(
            solver=self.name,
            status=status,
            reason=result.get("reason"),
            input_file=result.get("xml_path") or str(self.extraction_path),
            output_file=result.get("touchstone_path"),
            report_path=result.get("report_path"),
            parsed={"touchstone_path": result.get("touchstone_path")},
            validation=result.get("validation", {}),
        )

    def parse(self) -> SolverLifecycleResult:
        return _parse_report(self.name, self.report_path, "touchstone_path")

    def validate(self) -> SolverLifecycleResult:
        parsed = self.parse()
        ok = parsed.parsed.get("touchstone_path") is not None
        return parsed.model_copy(
            update={
                "status": "executed" if ok else "failed",
                "reason": None if ok else "openEMS produced no Touchstone output",
                "validation": {"has_touchstone": ok, **parsed.validation},
            }
        )


def _normalize_status(value: Any) -> SolverStatus:
    status = str(value or "").lower()
    if status in {"executed", "ok", "success", "passed"}:
        return "executed"
    if status in {"skipped", "skip"}:
        return "skipped"
    if status == "prepared":
        return "prepared"
    return "failed"


def _reason(result: dict[str, Any]) -> str | None:
    if result.get("reason"):
        return str(result["reason"])
    warnings = result.get("warnings")
    if isinstance(warnings, list) and warnings:
        return str(warnings[0])
    return None


def _parse_report(solver: str, report_path: Path, key: str) -> SolverLifecycleResult:
    if not report_path.is_file():
        return SolverLifecycleResult(
            solver=solver,
            status="failed",
            reason=f"report not found: {report_path}",
            report_path=str(report_path),
        )
    data = json.loads(report_path.read_text(encoding="utf-8"))
    status = _normalize_status(data.get("status"))
    return SolverLifecycleResult(
        solver=solver,
        status=status,
        reason=_reason(data),
        input_file=data.get("deck", {}).get("lst_path") or data.get("deck", {}).get("inp_path") or data.get("xml_path"),
        output_file=data.get("touchstone_path") or data.get("report_path"),
        report_path=str(report_path),
        parsed={key: data.get(key)},
        validation=data.get("validation", {}),
    )
