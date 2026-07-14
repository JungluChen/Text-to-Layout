"""``textlayout doctor`` — environment health check for a fresh clone.

Checks the hard requirements (Python version, package imports, output-directory
write permission) and reports optional external solvers honestly. A missing
optional solver is *never* a failure: the report says execution will be skipped
and solver input generation remains available.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DOCTOR_SCHEMA = "textlayout.doctor.v1"

#: Hard requirements: (check name, module to import).
_REQUIRED_IMPORTS: tuple[tuple[str, str], ...] = (
    ("textlayout", "textlayout"),
    ("gdsfactory", "gdsfactory"),
    ("klayout.db", "klayout.db"),
    ("langgraph.graph", "langgraph.graph"),
)

_FASTERCAP_ABSENT_MESSAGE = (
    "FasterCap/FastCap not found. Capacitance solver execution will be skipped. "
    "Solver input generation remains available. Physics verification will not be claimed."
)


@dataclass(slots=True)
class DoctorCheck:
    name: str
    status: str  # "ok" | "fail" | "absent"
    detail: str = ""
    required: bool = True
    section: str = "Core"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "required": self.required,
            "section": self.section,
        }


@dataclass(slots=True)
class DoctorReport:
    checks: list[DoctorCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.status == "ok" for check in self.checks if check.required)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": DOCTOR_SCHEMA,
            "status": "ok" if self.ok else "failed",
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "checks": [check.to_dict() for check in self.checks],
        }


def _check_python() -> DoctorCheck:
    ok = sys.version_info >= (3, 11)
    return DoctorCheck(
        name="Python",
        status="ok" if ok else "fail",
        detail=f"{sys.version.split()[0]} (requires >= 3.11)",
    )


def _check_import(
    name: str, module: str, *, required: bool = True, section: str = "Core"
) -> DoctorCheck:
    try:
        imported = importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 - report any import failure honestly
        return DoctorCheck(
            name=name,
            status="fail" if required else "absent",
            detail=f"import {module}: {exc}",
            required=required,
            section=section,
        )
    version = getattr(imported, "__version__", None)
    if version is None and "." in module:
        parent = importlib.import_module(module.split(".", 1)[0])
        version = getattr(parent, "__version__", None)
    return DoctorCheck(
        name=name,
        status="ok",
        detail=f"{module} {version or ''}".strip(),
        required=required,
        section=section,
    )


def _check_output_dir(output_dir: str | Path) -> DoctorCheck:
    target = Path(output_dir)
    try:
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target, prefix=".doctor-", delete=False) as probe:
            probe_path = Path(probe.name)
            probe.write(b"ok")
        probe_path.unlink(missing_ok=True)
    except OSError as exc:
        return DoctorCheck(
            name="output directory write permission",
            status="fail",
            detail=f"{target}: {exc}",
        )
    return DoctorCheck(
        name="output directory write permission", status="ok", detail=str(target.resolve())
    )


def _check_fastercap(*, strict: bool = False) -> DoctorCheck:
    from textlayout.simulation.fastercap import _find_solver

    found = _find_solver(os.environ.get("TEXTLAYOUT_FASTERCAP") or None)
    if found is None:
        return DoctorCheck(
            name="FasterCap/FastCap",
            status="absent",
            detail=_FASTERCAP_ABSENT_MESSAGE,
            required=strict,
            section="Extraction",
        )
    return DoctorCheck(
        name="FasterCap/FastCap",
        status="ok",
        detail=found,
        required=False,
        section="Extraction",
    )


def _external_check(
    name: str,
    finder: Any,
    *,
    section: str,
    required: bool,
) -> DoctorCheck:
    try:
        found = finder()
    except Exception as exc:  # noqa: BLE001 - discovery must never crash doctor
        return DoctorCheck(
            name=name,
            status="absent",
            detail=f"discovery error: {exc}",
            required=required,
            section=section,
        )
    return DoctorCheck(
        name=name,
        status="ok" if found else "absent",
        detail=str(found) if found else "not found; execution will be skipped honestly",
        required=required,
        section=section,
    )


def _optional_solver_checks(
    *, strict: bool = False, strict_em: bool = False, strict_fullchip: bool = False
) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    from textlayout.simulation.josim import _find as find_josim
    from textlayout.simulation.runners import (
        _FASTHENRY_NAMES,
        discover_openems_stack,
        find_executable,
    )
    from textlayout.simulation.wrspice import find_wrspice

    def find_palace() -> str | None:
        from textlayout.solvers.palace.capability import detect_palace

        capability = detect_palace()
        if not capability.available:
            return None
        identity = capability.executable or capability.container_image
        return f"{identity} (Palace {capability.version})"

    stack = discover_openems_stack()
    checks.append(
        _external_check(
            "FastHenry/FastHenry2",
            lambda: find_executable(_FASTHENRY_NAMES, env_var="TEXTLAYOUT_FASTHENRY"),
            section="Extraction",
            required=strict,
        )
    )
    for name, key in (
        ("openEMS", "openems"),
        ("CSXCAD", "csxcad"),
        ("Octave", "octave"),
        ("Octave openEMS path", "octave_openems_path"),
        ("Octave CSXCAD path", "octave_csxcad_path"),
    ):
        found = stack.get(key)
        checks.append(
            DoctorCheck(
                name=name,
                status="ok" if found else "absent",
                detail=str(found) if found else "not found; execution will be skipped honestly",
                required=strict or strict_em,
                section="RF / EM",
            )
        )
    checks.append(
        _check_import(
            "scikit-rf", "skrf", required=strict or strict_em, section="RF / EM"
        )
    )
    checks.extend(
        (
            _external_check(
                "Gmsh",
                lambda: find_executable(("gmsh", "gmsh.exe"), env_var="TEXTLAYOUT_GMSH"),
                section="3D FEM future",
                required=strict or strict_fullchip,
            ),
            _check_import(
                "meshio",
                "meshio",
                required=strict or strict_fullchip,
                section="3D FEM future",
            ),
            _external_check(
                "Palace",
                find_palace,
                section="3D FEM future",
                required=strict or strict_fullchip,
            ),
            _external_check(
                "JoSIM",
                lambda: find_josim(None),
                section="Circuit",
                required=strict,
            ),
            _external_check(
                "WRspice / ngspice",
                lambda: find_wrspice(None)
                or find_executable(("ngspice", "ngspice.exe"), env_var="TEXTLAYOUT_NGSPICE"),
                section="Circuit",
                required=strict,
            ),
        )
    )
    return checks


def run_doctor(
    output_dir: str | Path = "out",
    *,
    strict: bool = False,
    strict_em: bool = False,
    strict_fullchip: bool = False,
) -> DoctorReport:
    """Run every environment check and return the structured report."""
    report = DoctorReport()
    report.checks.append(_check_python())
    for name, module in _REQUIRED_IMPORTS:
        report.checks.append(_check_import(name, module))
    report.checks.append(_check_output_dir(output_dir))
    report.checks.append(_check_fastercap(strict=strict))
    report.checks.extend(
        _optional_solver_checks(
            strict=strict, strict_em=strict_em, strict_fullchip=strict_fullchip
        )
    )
    return report


def render_text(report: DoctorReport) -> str:
    marks = {"ok": "[ok]     ", "fail": "[FAIL]   ", "absent": "[missing]"}
    lines = ["textlayout doctor", ""]
    section: str | None = None
    for check in report.checks:
        if check.section != section:
            if section is not None:
                lines.append("")
            section = check.section
            lines.append(f"[{section}]")
        lines.append(f"{marks[check.status]} {check.name}: {check.detail}")
    lines.append("")
    lines.append(
        "Environment OK." if report.ok else "Environment has failures; see [FAIL] lines above."
    )
    lines.append(
        "Optional solvers marked [missing] cause honest SKIPPED_SOLVER_ABSENT evidence, "
        "never fake results."
    )
    return "\n".join(lines)
