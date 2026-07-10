"""Small workflow command entry points for installed Text-to-GDS skills."""

from __future__ import annotations

import argparse
import json
from typing import Any


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _workflow_main(name: str, role: str) -> None:
    parser = argparse.ArgumentParser(prog=name, description=role)
    parser.add_argument("--check", action="store_true", help="print workflow metadata and exit")
    args = parser.parse_args()
    _print(
        {
            "command": name,
            "role": role,
            "status": "ready" if args.check else "metadata",
            "evidence_contract": "SOLVER_EVIDENCE_CONTRACT.md",
            "signoff_criteria": "SIGNOFF_CRITERIA.md",
        }
    )


def text_to_gds_simulation() -> None:
    _workflow_main("text-to-gds-simulation", "solver handoff and execution evidence")


def text_to_gds_circuit_design() -> None:
    _workflow_main("text-to-gds-circuit-design", "pre-layout circuit intent and feasibility")


def text_to_gds_layout_design() -> None:
    _workflow_main("text-to-gds-layout-design", "layout generation, DRC, extraction, physics graph")


def text_to_gds_signoff() -> None:
    _workflow_main("text-to-gds-signoff", "artifact audit and Level 0-6 signoff evaluation")


def text_to_gds_physics_signoff() -> None:
    _workflow_main("text-to-gds-physics-signoff", "Level 5+ physics signoff audit")

