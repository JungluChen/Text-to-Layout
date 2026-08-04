"""``textlayout doctor`` — environment health check for a fresh clone.

Checks the hard requirements (Python version, package imports, output-directory
write permission) and reports optional external solvers honestly. A missing
optional solver is *never* a failure: the report says execution will be skipped
and solver input generation remains available.
"""

from __future__ import annotations

import importlib
import hashlib
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textlayout.platform_support import PlatformSupportState, SolverEvidenceStage

DOCTOR_SCHEMA = "textlayout.doctor.v2"

FOUND = "FOUND"
MISSING = "MISSING"
BROKEN = "BROKEN"
WRONG_VERSION = "WRONG_VERSION"
CONTAINER_AVAILABLE = "CONTAINER_AVAILABLE"
NOT_SUPPORTED_ON_PLATFORM = "NOT_SUPPORTED_ON_PLATFORM"
NOT_TESTED_ON_PLATFORM = "NOT_TESTED_ON_PLATFORM"

_PASSING_STATUSES = {FOUND, CONTAINER_AVAILABLE}

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
    status: str
    detail: str = ""
    required: bool = True
    section: str = "Core"
    path: str | None = None
    version: str | None = None
    backend_type: str | None = None
    capabilities: list[str] = field(default_factory=list)
    smoke_test: str | None = None
    executable_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "required": self.required,
            "section": self.section,
            "path": self.path,
            "version": self.version,
            "backend_type": self.backend_type,
            "capabilities": self.capabilities,
            "smoke_test": self.smoke_test,
            "executable_sha256": self.executable_sha256,
        }


@dataclass(slots=True)
class DoctorReport:
    checks: list[DoctorCheck] = field(default_factory=list)
    system: dict[str, Any] = field(default_factory=dict)
    physics_capabilities: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(check.status in _PASSING_STATUSES for check in self.checks if check.required)

    def to_dict(self) -> dict[str, Any]:
        core = {check.name: check.to_dict() for check in self.checks if check.section == "Core"}
        external = {
            check.name: {
                **check.to_dict(),
                "evidence_stage": _solver_evidence_stage(check).value,
                "support_state": _solver_support_state(check).value,
            }
            for check in self.checks
            if check.section != "Core"
        }
        return {
            "schema": DOCTOR_SCHEMA,
            "status": "ok" if self.ok else "failed",
            "host": {
                "os": self.system["os"],
                "os_release": self.system["os_release"],
                "architecture": self.system["architecture"],
                "filesystem": self.system["filesystem"],
            },
            "runtime": {
                "python": self.system["python"],
                "textlayout": self.system["package_version"],
                "git_sha": self.system["package_commit"],
                "support_state": (
                    PlatformSupportState.CORE_TESTED if self.ok else PlatformSupportState.UNTESTED
                ).value,
            },
            "wsl": self.system["wsl"],
            "core_dependencies": core,
            "external_solvers": external,
            "capabilities": _capability_report(self.checks, core_ok=self.ok),
            # Compatibility views retained for existing consumers.
            "system": self.system,
            "physics_capabilities": self.physics_capabilities,
            "checks": [check.to_dict() for check in self.checks],
        }


def _solver_evidence_stage(check: DoctorCheck) -> SolverEvidenceStage:
    if check.status in {FOUND, CONTAINER_AVAILABLE}:
        return SolverEvidenceStage.PROBE_PASS
    if check.path:
        return SolverEvidenceStage.FOUND
    return SolverEvidenceStage.NOT_INSTALLED


def _solver_support_state(check: DoctorCheck) -> PlatformSupportState:
    if check.status == NOT_SUPPORTED_ON_PLATFORM:
        return PlatformSupportState.UNSUPPORTED
    if _solver_evidence_stage(check) is SolverEvidenceStage.PROBE_PASS:
        return PlatformSupportState.SOLVER_PARTIAL
    return PlatformSupportState.UNTESTED


def _file_sha256(path: str | Path | None) -> str | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _check_python() -> DoctorCheck:
    ok = sys.version_info >= (3, 11)
    return DoctorCheck(
        name="Python",
        status=FOUND if ok else WRONG_VERSION,
        detail=f"{sys.version.split()[0]} (requires >= 3.11)",
        version=sys.version.split()[0],
        backend_type="runtime",
        smoke_test="passed" if ok else "failed: unsupported version",
    )


def _check_import(
    name: str, module: str, *, required: bool = True, section: str = "Core"
) -> DoctorCheck:
    try:
        imported = importlib.import_module(module)
    except ModuleNotFoundError as exc:
        return DoctorCheck(
            name=name,
            status=MISSING,
            detail=f"import {module}: {exc}",
            required=required,
            section=section,
            backend_type="python-package",
            smoke_test="failed: module not found",
        )
    except Exception as exc:  # noqa: BLE001 - report any import failure honestly
        return DoctorCheck(
            name=name,
            status=BROKEN,
            detail=f"import {module}: {exc}",
            required=required,
            section=section,
            backend_type="python-package",
            smoke_test=f"failed: {type(exc).__name__}",
        )
    version = getattr(imported, "__version__", None)
    if version is None and "." in module:
        parent = importlib.import_module(module.split(".", 1)[0])
        version = getattr(parent, "__version__", None)
    return DoctorCheck(
        name=name,
        status=FOUND,
        detail=f"{module} {version or ''}".strip(),
        required=required,
        section=section,
        path=str(getattr(imported, "__file__", "")) or None,
        version=str(version) if version is not None else None,
        backend_type="python-package",
        smoke_test="passed: imported",
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
            status=BROKEN,
            detail=f"{target}: {exc}",
            path=str(target),
            backend_type="filesystem",
            smoke_test=f"failed: {type(exc).__name__}",
        )
    return DoctorCheck(
        name="output directory write permission",
        status=FOUND,
        detail=str(target.resolve()),
        path=str(target.resolve()),
        backend_type="filesystem",
        smoke_test="passed: create/write/delete",
    )


def _check_fastercap(*, strict: bool = False) -> DoctorCheck:
    from textlayout.simulation.fastercap import _capture_solver_version, _find_solver

    found = _find_solver(os.environ.get("TEXTLAYOUT_FASTERCAP") or None)
    if found is None:
        return DoctorCheck(
            name="FasterCap/FastCap",
            status=MISSING,
            detail=_FASTERCAP_ABSENT_MESSAGE,
            required=strict,
            section="Extraction",
            backend_type="executable",
            capabilities=["IDC electrostatics", "capacitance matrix"],
            smoke_test="not run: executable missing",
        )
    version = _capture_solver_version(found, Path.cwd())
    if version is None:
        return DoctorCheck(
            name="FasterCap/FastCap",
            status=BROKEN,
            detail=f"found {found}, but the deterministic -bv/-v probe returned no banner",
            required=strict,
            section="Extraction",
            path=found,
            backend_type="executable",
            capabilities=["IDC electrostatics", "capacitance matrix"],
            smoke_test="failed: version probe",
        )
    return DoctorCheck(
        name="FasterCap/FastCap",
        status=FOUND,
        detail=f"{found} ({version})",
        required=False,
        section="Extraction",
        path=found,
        version=version,
        backend_type="executable",
        capabilities=["IDC electrostatics", "capacitance matrix"],
        smoke_test="passed: process launched and returned a version banner",
        executable_sha256=_file_sha256(found),
    )


def _probe_executable(executable: str) -> str | None:
    """Launch an executable with bounded non-mutating version/help probes."""
    from textlayout.simulation.runners import _execution_command

    flags: tuple[str, ...] = ("--version", "-v", "--help", "-h")
    if "fastercap" in Path(executable).name.lower():
        flags = ("-bv", *flags)
    for flag in flags:
        try:
            completed = subprocess.run(
                _execution_command(executable, [flag], Path.cwd()),
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        banner = (completed.stdout or completed.stderr).strip()
        if banner:
            return banner.splitlines()[0][:200]
    return None


def _external_check(
    name: str,
    finder: Any,
    *,
    section: str,
    required: bool,
    capabilities: tuple[str, ...] = (),
) -> DoctorCheck:
    try:
        found = finder()
    except Exception as exc:  # noqa: BLE001 - discovery must never crash doctor
        return DoctorCheck(
            name=name,
            status=BROKEN,
            detail=f"discovery error: {exc}",
            required=required,
            section=section,
            backend_type="executable",
            capabilities=list(capabilities),
            smoke_test=f"failed: discovery raised {type(exc).__name__}",
        )
    if not found:
        return DoctorCheck(
            name=name,
            status=MISSING,
            detail="not found; execution will be skipped honestly",
            required=required,
            section=section,
            backend_type="executable",
            capabilities=list(capabilities),
            smoke_test="not run: executable missing",
        )
    executable = str(found)
    version = _probe_executable(executable)
    if version is None:
        return DoctorCheck(
            name=name,
            status=BROKEN,
            detail=f"found {executable}, but no deterministic version/help probe succeeded",
            required=required,
            section=section,
            path=executable,
            backend_type="executable",
            capabilities=list(capabilities),
            smoke_test="failed: process/version probe",
        )
    return DoctorCheck(
        name=name,
        status=FOUND,
        detail=f"{executable} ({version})",
        required=required,
        section=section,
        path=executable,
        version=version,
        backend_type="executable",
        capabilities=list(capabilities),
        smoke_test="passed: process launched and returned a version/help banner",
        executable_sha256=_file_sha256(executable),
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

    stack = discover_openems_stack()
    checks.append(
        _external_check(
            "FastHenry/FastHenry2",
            lambda: find_executable(_FASTHENRY_NAMES, env_var="TEXTLAYOUT_FASTHENRY"),
            section="Extraction",
            required=strict,
            capabilities=("Spiral PEEC", "inductance matrix"),
        )
    )
    for name, key, capabilities in (
        ("openEMS", "openems", ("CPW FDTD",)),
        ("CSXCAD", "csxcad", ("CPW FDTD geometry",)),
        ("Octave", "octave", ("openEMS frontend",)),
    ):
        found = stack.get(key)
        checks.append(
            _external_check(
                name,
                lambda found=found: found,
                required=strict or strict_em,
                section="RF / EM",
                capabilities=capabilities,
            )
        )
    for name, key in (
        ("Octave openEMS path", "octave_openems_path"),
        ("Octave CSXCAD path", "octave_csxcad_path"),
    ):
        found = stack.get(key)
        checks.append(
            DoctorCheck(
                name=name,
                status=FOUND if found else MISSING,
                detail=str(found) if found else "not found; execution will be skipped honestly",
                required=strict or strict_em,
                section="RF / EM",
                path=str(found) if found else None,
                backend_type="interface-directory",
                capabilities=["CPW FDTD"],
                smoke_test="passed: discovered interface directory"
                if found
                else "not run: missing",
            )
        )
    checks.append(
        _check_import("scikit-rf", "skrf", required=strict or strict_em, section="RF / EM")
    )
    checks.extend(
        (
            _external_check(
                "Gmsh",
                lambda: find_executable(("gmsh", "gmsh.exe"), env_var="TEXTLAYOUT_GMSH"),
                section="3D FEM future",
                required=strict or strict_fullchip,
                capabilities=("3D meshing",),
            ),
            _check_import(
                "meshio",
                "meshio",
                required=strict or strict_fullchip,
                section="3D FEM future",
            ),
            _external_check(
                "JoSIM",
                lambda: find_josim(None),
                section="Circuit",
                required=strict,
                capabilities=("Josephson transient",),
            ),
            _external_check(
                "WRspice / ngspice",
                lambda: (
                    find_wrspice(None)
                    or find_executable(("ngspice", "ngspice.exe"), env_var="TEXTLAYOUT_NGSPICE")
                ),
                section="Circuit",
                required=strict,
                capabilities=("Josephson harmonic balance", "SPICE transient"),
            ),
        )
    )
    from textlayout.solvers.palace.capability import detect_palace

    palace = detect_palace()
    if not palace.available:
        palace_check = DoctorCheck(
            name="Palace",
            status=MISSING,
            detail=palace.unavailable_reason or "not found",
            required=strict or strict_fullchip,
            section="3D FEM future",
            backend_type="executable-or-container",
            capabilities=["Eigenmode FEM"],
            smoke_test="not run: backend missing",
        )
    else:
        is_container = palace.execution_kind == "container"
        identity = palace.container_image if is_container else palace.executable
        identified = bool(palace.container_digest if is_container else palace.executable_sha256)
        probe_ok = identified and palace.version is not None
        palace_check = DoctorCheck(
            name="Palace",
            status=(CONTAINER_AVAILABLE if is_container else FOUND) if probe_ok else BROKEN,
            detail=(
                f"{identity} (Palace {palace.version})"
                if probe_ok
                else f"found {identity}, but identity/version probing was incomplete"
            ),
            required=strict or strict_fullchip,
            section="3D FEM future",
            path=identity,
            version=palace.version,
            backend_type=str(palace.execution_kind),
            capabilities=["Eigenmode FEM"],
            smoke_test=(
                "passed: immutable identity and version probe"
                if probe_ok
                else "failed: identity/version probe"
            ),
            executable_sha256=(
                palace.executable_sha256 if not is_container else palace.container_digest
            ),
        )
    checks.insert(-2, palace_check)
    return checks


def _git_commit() -> str:
    from textlayout._paths import repository_root

    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root()), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    commit = completed.stdout.strip()
    return commit if len(commit) == 40 else "unknown"


def _wsl_system() -> dict[str, Any]:
    release = platform.release()
    is_wsl = bool(os.environ.get("WSL_INTEROP")) or "microsoft" in release.lower()
    distro = os.environ.get("WSL_DISTRO_NAME") if is_wsl else None
    version: int | None = None
    if is_wsl:
        version = 2 if "wsl2" in release.lower() or "microsoft-standard" in release.lower() else 1
    cwd = str(Path.cwd().resolve())
    filesystem_warning = None
    if is_wsl and cwd.startswith("/mnt/"):
        filesystem_warning = (
            "Repository is on a Windows-mounted filesystem. Put heavy FEM build and solve "
            "directories on WSL-native ext4 (for example under $HOME)."
        )
    return {
        "detected": is_wsl,
        "version": version,
        "distro": distro,
        "filesystem_warning": filesystem_warning,
    }


def _system_report() -> dict[str, Any]:
    from textlayout import __version__

    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python": sys.version.split()[0],
        "package_commit": _git_commit(),
        "package_version": __version__,
        "filesystem": str(Path.cwd().resolve()),
        "wsl": _wsl_system(),
    }


def _physics_capabilities(checks: list[DoctorCheck]) -> dict[str, str]:
    by_name = {check.name: check for check in checks}

    def state(*names: str) -> str:
        selected = [by_name[name] for name in names]
        if all(check.status in {FOUND, CONTAINER_AVAILABLE} for check in selected):
            return "PROBE_PASS_ONLY"
        if any(check.status == BROKEN for check in selected):
            return "INCOMPLETE"
        if any(check.status == CONTAINER_AVAILABLE for check in selected):
            return "PROBE_PASS_ONLY"
        if all(check.status == MISSING for check in selected):
            return "NOT_INSTALLED"
        return "INCOMPLETE"

    return {
        "IDC electrostatics": state("FasterCap/FastCap"),
        "CPW FDTD": state(
            "openEMS",
            "CSXCAD",
            "Octave",
            "Octave openEMS path",
            "Octave CSXCAD path",
            "scikit-rf",
        ),
        "Spiral PEEC": state("FastHenry/FastHenry2"),
        "Eigenmode FEM": state("Gmsh", "meshio", "Palace"),
        "Josephson transient": state("JoSIM"),
        "Josephson harmonic balance": state("WRspice / ngspice"),
    }


def _capability_report(checks: list[DoctorCheck], *, core_ok: bool) -> dict[str, dict[str, str]]:
    by_name = {check.name: check for check in checks}

    def numerical(*names: str) -> str:
        selected = [by_name[name] for name in names]
        if all(check.status in {FOUND, CONTAINER_AVAILABLE} for check in selected):
            return "PROBE_PASS_ONLY"
        if all(check.status == MISSING for check in selected):
            return "BLOCKED_SOLVER_ABSENT"
        return "BLOCKED_STACK_INCOMPLETE"

    return {
        "Layout generation": {
            "state": "READY" if core_ok else "BLOCKED_CORE",
            "support_state": (
                PlatformSupportState.CORE_TESTED if core_ok else PlatformSupportState.UNTESTED
            ).value,
        },
        "KLayout verification": {
            "state": "READY" if by_name["klayout.db"].status == FOUND else "BLOCKED_CORE",
            "support_state": (
                PlatformSupportState.CORE_TESTED
                if by_name["klayout.db"].status == FOUND
                else PlatformSupportState.UNTESTED
            ).value,
        },
        "IDC analytical": {
            "state": "READY" if core_ok else "BLOCKED_CORE",
            "support_state": PlatformSupportState.CORE_TESTED.value,
        },
        "IDC BEM": {
            "state": numerical("FasterCap/FastCap"),
            "support_state": _solver_support_state(by_name["FasterCap/FastCap"]).value,
        },
        "CPW full-wave": {
            "state": numerical(
                "openEMS",
                "CSXCAD",
                "Octave",
                "Octave openEMS path",
                "Octave CSXCAD path",
                "scikit-rf",
            ),
            "support_state": PlatformSupportState.UNTESTED.value,
        },
        "Spiral PEEC": {
            "state": numerical("FastHenry/FastHenry2"),
            "support_state": _solver_support_state(by_name["FastHenry/FastHenry2"]).value,
        },
        "Resonator FEM": {
            "state": numerical("Gmsh", "meshio", "Palace"),
            "support_state": PlatformSupportState.UNTESTED.value,
        },
        "JJ transient": {
            "state": numerical("JoSIM"),
            "support_state": _solver_support_state(by_name["JoSIM"]).value,
        },
    }


def run_doctor(
    output_dir: str | Path = "out",
    *,
    strict: bool = False,
    strict_em: bool = False,
    strict_fullchip: bool = False,
) -> DoctorReport:
    """Run every environment check and return the structured report."""
    report = DoctorReport(system=_system_report())
    report.checks.append(_check_python())
    for name, module in _REQUIRED_IMPORTS:
        report.checks.append(_check_import(name, module))
    report.checks.append(_check_output_dir(output_dir))
    report.checks.append(_check_fastercap(strict=strict))
    report.checks.extend(
        _optional_solver_checks(strict=strict, strict_em=strict_em, strict_fullchip=strict_fullchip)
    )
    report.physics_capabilities = _physics_capabilities(report.checks)
    return report


def render_text(report: DoctorReport) -> str:
    structured = report.to_dict()
    lines = ["TEXT-TO-LAYOUT DOCTOR 2.0", "", "[Host]"]
    lines.extend(
        (
            f"OS: {report.system['os']} {report.system['os_release']}",
            f"architecture: {report.system['architecture']}",
            f"Python: {report.system['python']}",
            f"package commit: {report.system['package_commit']}",
            f"filesystem: {report.system['filesystem']}",
            "",
            "[Runtime]",
            f"Text-to-Layout: {report.system['package_version']}",
            f"support state: {structured['runtime']['support_state']}",
        )
    )
    wsl = report.system["wsl"]
    if wsl["detected"]:
        lines.append(f"WSL: version={wsl['version']} distro={wsl['distro'] or 'unknown'}")
        if wsl["filesystem_warning"]:
            lines.append(f"WARNING: {wsl['filesystem_warning']}")
    lines.append("")
    section: str | None = None
    for check in report.checks:
        if check.section != section:
            if section is not None:
                lines.append("")
            section = check.section
            lines.append(f"[{section}]")
        lines.append(f"[{check.status}] {check.name}: {check.detail}")
    lines.extend(("", "[Capabilities]"))
    width = max(len(name) for name in structured["capabilities"])
    for name, record in structured["capabilities"].items():
        lines.append(f"{name.ljust(width)}  {record['state']}")
    lines.append("")
    lines.append(
        "Environment OK." if report.ok else "Environment has failures; see [FAIL] lines above."
    )
    lines.append(
        "Optional solvers marked [MISSING] cause honest SKIPPED_SOLVER_ABSENT evidence, "
        "never fake results."
    )
    return "\n".join(lines)
