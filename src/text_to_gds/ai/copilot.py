from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from text_to_gds.ai.design_intent import DesignIntent, DesignIntentParser
from text_to_gds.layout.technology import TechnologyFactory


@runtime_checkable
class SolverAdapter(Protocol):
    @property
    def name(self) -> str: ...
    def is_available(self) -> bool: ...
    def execute(
        self,
        input_data: dict[str, Any],
        *,
        output_dir: Path | None = None,
    ) -> Any: ...


@dataclass
class CopilotResult:
    status: str
    intent: DesignIntent | None
    gds_path: Path | None
    extraction: dict[str, Any] | None
    simulations: dict[str, Any] | None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "intent": self.intent.to_dict() if self.intent is not None else None,
            "gds_path": str(self.gds_path) if self.gds_path is not None else None,
            "extraction": self.extraction,
            "simulations": self.simulations,
            "errors": list(self.errors),
        }


class AICopilot:
    def __init__(self, technology: str = "gdsfactory") -> None:
        self.technology = technology
        self._selector = TechnologyFactory.create(technology)
        self._parser = DesignIntentParser()
        self.solvers: dict[str, SolverAdapter] = {}

    def register_solver(self, name: str, adapter: SolverAdapter) -> None:
        self.solvers[name] = adapter

    def execute(self, prompt: str) -> CopilotResult:
        errors: list[str] = []

        intent = self._parser.parse(prompt, technology=self.technology)
        if intent.device == "unknown":
            errors.append("could not determine device from prompt")

        gds_path: Path | None = None
        extraction: dict[str, Any] | None = None
        simulations: dict[str, Any] | None = None

        if not self.solvers:
            errors.append("no solvers registered")

        status = "success" if not errors else "partial"

        return CopilotResult(
            status=status,
            intent=intent,
            gds_path=gds_path,
            extraction=extraction,
            simulations=simulations,
            errors=errors,
        )
