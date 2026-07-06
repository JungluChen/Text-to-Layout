"""Graceful execution of open-source solvers with strict status discipline.

Every runner follows the same contract so the workflow never crashes on a
missing solver and never overclaims:

* detect the solver; return ``solver_missing`` (status ``skipped``) if absent,
* execute it on the already-prepared input files,
* parse the solver-owned output; return ``failed_gracefully`` on any problem,
* compare the parsed value against the target,
* set ``within_tolerance`` so ``SimulationResult.physics_verified`` can gate.

``physics_verified`` is *only* reachable when a real solver produced a non-empty
output, a value was parsed, and the comparison is within tolerance.
"""

from __future__ import annotations

import math
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

from textlayout.simulation.models import SimulationResult, target_comparison as _compare
from textlayout.solvers.base import run_subprocess


_ROOT = Path(__file__).resolve().parents[3]
_WSL_PREFIX = "wsl:"


def _windows_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive}/{tail}"


def _is_elf(path: Path) -> bool:
    try:
        return path.read_bytes()[:4] == b"\x7fELF"
    except OSError:
        return False


def _wsl_exe() -> str | None:
    """Full path to wsl.exe, resolved via Python's os.environ PATH snapshot.

    Never launch bare ``"wsl"``: native libraries (gmsh.initialize() is the
    known offender) can truncate the Win32-level PATH with a fixed-size
    buffer, silently dropping System32 from CreateProcess's search path while
    shutil.which — which reads Python's os.environ copy — still resolves it.
    """
    if os.name != "nt":
        return None
    return shutil.which("wsl")


def _wsl_which(names: tuple[str, ...]) -> str | None:
    wsl = _wsl_exe()
    if wsl is None:
        return None
    expression = " || ".join(f"command -v {shlex.quote(name)}" for name in names)
    try:
        completed = subprocess.run(
            [wsl, "bash", "-lc", expression],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        # WSL discovery must degrade to "not found", never crash the caller.
        return None
    found = completed.stdout.strip().splitlines()
    return f"{_WSL_PREFIX}{found[0]}" if completed.returncode == 0 and found else None


def find_executable(
    names: tuple[str, ...],
    explicit: str | None = None,
    *,
    env_var: str | None = None,
) -> str | None:
    """Resolve explicit, environment, PATH, local ``.tools``, then WSL binaries."""
    if explicit:
        if explicit.startswith(_WSL_PREFIX):
            return explicit
        path = Path(explicit)
        if path.is_file():
            return f"{_WSL_PREFIX}{_windows_to_wsl(path)}" if _is_elf(path) else str(path)
        if explicit.startswith("/mnt/"):
            return f"{_WSL_PREFIX}{explicit}"
        return shutil.which(explicit)
    if env_var and os.environ.get(env_var):
        return find_executable(names, os.environ[env_var])
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    tools = _ROOT / ".tools"
    if tools.is_dir():
        for name in names:
            candidates = {
                *tools.glob(name),
                *tools.glob(f"*/bin/{name}"),
                *tools.glob(f"*/*/{name}"),
            }
            for candidate in sorted(candidates):
                try:
                    is_file = candidate.is_file()
                except OSError:
                    continue
                if not is_file:
                    continue
                if _is_elf(candidate):
                    return f"{_WSL_PREFIX}{_windows_to_wsl(candidate)}"
                return str(candidate)
    return _wsl_which(names)


def _execution_command(solver: str, args: list[str], cwd: Path) -> list[str]:
    if not solver.startswith(_WSL_PREFIX):
        return [solver, *args]
    executable = solver.removeprefix(_WSL_PREFIX)
    workdir = _windows_to_wsl(cwd)
    command = " ".join([shlex.quote(executable), *(shlex.quote(arg) for arg in args)])
    return [_wsl_exe() or "wsl", "bash", "-lc", f"cd {shlex.quote(workdir)} && {command}"]


def _skipped(prepared: SimulationResult, names: tuple[str, ...]) -> SimulationResult:
    return SimulationResult(
        status="skipped",
        solver=prepared.solver,
        readiness_level=prepared.readiness_level,
        reason=(
            f"{prepared.solver} executable not found (looked for {', '.join(names)}). "
            "Install it or pass an explicit path; prepared input files remain available."
        ),
        output_dir=prepared.output_dir,
        artifacts=dict(prepared.artifacts),
        warnings=prepared.warnings,
    )


def _failed(prepared: SimulationResult, reason: str, **extra: Any) -> SimulationResult:
    return SimulationResult(
        status="failed",
        solver=prepared.solver,
        readiness_level=prepared.readiness_level,
        reason=reason,
        output_dir=prepared.output_dir,
        artifacts={**prepared.artifacts, **{k: str(v) for k, v in extra.items()}},
        warnings=prepared.warnings,
    )


# --- FastHenry (inductance) ---------------------------------------------------
_FASTHENRY_NAMES = ("fasthenry", "fasthenry.exe", "FastHenry", "FastHenry2", "fasthenry2")


def run_fasthenry(
    prepared: SimulationResult,
    *,
    target_inductance_h: float | None = None,
    tolerance_pct: float = 5.0,
    executable: str | None = None,
    timeout_seconds: int = 600,
) -> SimulationResult:
    """Execute FastHenry on a prepared ``.inp`` and extract the inductance."""
    input_path = Path(prepared.artifacts.get("input", ""))
    if not input_path.is_file():
        return _failed(prepared, "No FastHenry .inp input was prepared.")
    solver = find_executable(
        _FASTHENRY_NAMES, executable, env_var="TEXTLAYOUT_FASTHENRY"
    )
    if solver is None:
        return _skipped(prepared, _FASTHENRY_NAMES)

    work = input_path.parent
    try:
        completed = run_subprocess(
            _execution_command(solver, [input_path.name], work),
            cwd=work,
            timeout_seconds=timeout_seconds,
            log_prefix="fasthenry",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _failed(prepared, f"FastHenry execution failed: {exc}")

    zc = work / "Zc.mat"
    if completed.returncode != 0 or not zc.is_file():
        return _failed(
            prepared,
            f"FastHenry exited {completed.returncode} without a Zc.mat output.",
            solver_stdout=completed.stdout_path,
            solver_stderr=completed.stderr_path,
        )
    try:
        inductance_h = parse_fasthenry_inductance(zc.read_text(encoding="utf-8"))
    except ValueError as exc:
        return _failed(prepared, f"Could not parse FastHenry Zc.mat: {exc}", zc_matrix=zc)

    extracted = {"inductance_h": inductance_h, "inductance_nh": inductance_h * 1e9}
    comparison = _compare(inductance_h, target_inductance_h, tolerance_pct, "inductance_h")
    return SimulationResult(
        status="executed",
        solver=Path(solver).name,
        readiness_level=4 if comparison else 3,
        reason="FastHenry returned a parseable impedance matrix.",
        output_dir=prepared.output_dir,
        artifacts={
            **prepared.artifacts,
            "solver_stdout": str(completed.stdout_path),
            "solver_stderr": str(completed.stderr_path),
            "zc_matrix": str(zc),
            "result": str(zc),
        },
        extracted_quantities=extracted,
        target_comparison=comparison,
        warnings=prepared.warnings,
        command=completed.command,
        return_code=completed.returncode,
        runtime_seconds=completed.runtime_seconds,
        solver_version="FastHenry 3.0.1",
    )


def parse_fasthenry_inductance(text: str) -> float:
    """Inductance (H) from the lowest-frequency block of a FastHenry Zc.mat.

    Zc.mat blocks look like::

        Impedance matrix for frequency = 1e+06 1 x 1
        2.5e-03    6.2832e-03

    where each entry is ``Re Im`` of Z. L = Im(Z) / (2*pi*f).
    """
    lines = text.splitlines()
    frequency: float | None = None
    number_re = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
    for index, line in enumerate(lines):
        match = re.search(r"frequency\s*=\s*([0-9.eE+-]+)", line)
        if match is None:
            continue
        frequency = float(match.group(1))
        # The impedance row is the next non-empty data line (Re Im).
        for entry in lines[index + 1 :]:
            numbers = number_re.findall(entry)
            if len(numbers) >= 2:
                reactance = float(numbers[1])
                if frequency <= 0:
                    raise ValueError("non-positive frequency")
                return reactance / (2.0 * math.pi * frequency)
        break
    if frequency is None:
        raise ValueError("no frequency header found")
    raise ValueError("no impedance entry after header")


# --- openEMS (S-parameters / resonance) via scikit-rf -------------------------
_OPENEMS_NAMES = ("octave-cli", "octave-cli.exe", "octave", "octave.exe")


def discover_openems_stack() -> dict[str, str | None]:
    """Discover the openEMS core, CSXCAD viewer, and Octave frontend independently."""
    openems_matlab = _find_interface_directory("openEMS")
    csxcad_matlab = _find_interface_directory("CSXCAD")
    return {
        "openems": find_executable(
            ("openEMS", "openEMS.exe", "openems"), env_var="TEXTLAYOUT_OPENEMS_CORE"
        ),
        "csxcad": find_executable(
            ("AppCSXCAD", "AppCSXCAD.exe"), env_var="TEXTLAYOUT_CSXCAD"
        ),
        "octave": find_executable(_OPENEMS_NAMES, env_var="TEXTLAYOUT_OPENEMS"),
        "octave_openems_path": openems_matlab,
        "octave_csxcad_path": csxcad_matlab,
    }


def _find_interface_directory(project: str) -> str | None:
    """Locate a repo-local or WSL Octave interface directory."""
    tools = _ROOT / ".tools"
    if tools.is_dir():
        marker_name = "InitFDTD.m" if project == "openEMS" else "InitCSX.m"
        preferred = tools / "openems-wsl" / "share" / project / "matlab" / marker_name
        markers = [preferred] if preferred.is_file() else []
        markers.extend(sorted(tools.glob(f"*/share/{project}/matlab/{marker_name}")))
        markers.extend(sorted(tools.glob(f"*/*/matlab/{marker_name}")))
        for marker in dict.fromkeys(markers):
            directory = marker.parent
            return f"{_WSL_PREFIX}{_windows_to_wsl(directory)}"
    wsl = _wsl_exe()
    if wsl is not None:
        candidates = (
            f"/usr/share/{project}/matlab",
            f"/usr/local/share/{project}/matlab",
            f"/opt/share/{project}/matlab",
        )
        expression = " || ".join(
            f"test -d {shlex.quote(path)} && printf '%s\\n' {shlex.quote(path)}"
            for path in candidates
        )
        try:
            completed = subprocess.run(
                [wsl, "bash", "-lc", expression],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except OSError:
            return None
        found = completed.stdout.strip().splitlines()
        if found:
            return f"{_WSL_PREFIX}{found[0]}"
    return None


def run_openems(
    prepared: SimulationResult,
    *,
    target_frequency_ghz: float | None = None,
    tolerance_pct: float = 5.0,
    touchstone: str | Path | None = None,
    executable: str | None = None,
    timeout_seconds: int = 1800,
) -> SimulationResult:
    """Execute the generated openEMS Octave driver and parse Touchstone output."""
    s2p = _find_touchstone(prepared, touchstone)
    if s2p is None:
        stack = discover_openems_stack()
        solver = find_executable(_OPENEMS_NAMES, executable, env_var="TEXTLAYOUT_OPENEMS")
        if solver is None:
            return _skipped(prepared, _OPENEMS_NAMES)
        missing = [
            name
            for name in ("openems", "octave_openems_path", "octave_csxcad_path")
            if not stack.get(name)
        ]
        if missing:
            return SimulationResult(
                status="skipped",
                solver=prepared.solver,
                readiness_level=prepared.readiness_level,
                reason=f"openEMS stack incomplete: missing {', '.join(missing)}.",
                output_dir=prepared.output_dir,
                artifacts=dict(prepared.artifacts),
                warnings=prepared.warnings,
            )
        driver = Path(prepared.artifacts.get("driver", ""))
        if not driver.is_file():
            return _failed(prepared, "No runnable openEMS Octave driver was prepared.")
        try:
            completed = run_subprocess(
                _execution_command(solver, ["--quiet", "--no-gui", driver.name], driver.parent),
                cwd=driver.parent,
                timeout_seconds=timeout_seconds,
                log_prefix="solver",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _failed(prepared, f"openEMS execution failed: {exc}")
        artifacts = {
            **prepared.artifacts,
            "solver_stdout": str(completed.stdout_path),
            "solver_stderr": str(completed.stderr_path),
        }
        if completed.returncode != 0:
            return SimulationResult(
                status="failed",
                solver=prepared.solver,
                readiness_level=prepared.readiness_level,
                reason=f"openEMS Octave driver exited with code {completed.returncode}.",
                output_dir=prepared.output_dir,
                artifacts=artifacts,
                warnings=prepared.warnings,
                command=completed.command,
            )
        s2p = _find_touchstone(prepared, None)
        if s2p is None:
            return SimulationResult(
                status="failed",
                solver=prepared.solver,
                readiness_level=prepared.readiness_level,
                reason="openEMS completed without a non-empty Touchstone output.",
                output_dir=prepared.output_dir,
                artifacts=artifacts,
                warnings=prepared.warnings,
                command=completed.command,
            )
    else:
        artifacts = dict(prepared.artifacts)
        completed = None
    try:
        component = _prepared_component(prepared)
        if component == "CPW":
            extracted = extract_cpw_from_touchstone(s2p, target_frequency_ghz)
            metrics = Path(prepared.output_dir or s2p.parent) / "openems_metrics.csv"
            if metrics.is_file() and metrics.stat().st_size:
                extracted.update(_extract_openems_cpw_metrics(metrics, target_frequency_ghz))
                artifacts["metrics_csv"] = str(metrics)
            quantity = "characteristic_impedance_ohm"
            value = extracted[quantity]
        else:
            extracted = extract_resonance_metrics_from_touchstone(s2p)
            value = extracted["resonance_frequency_ghz"]
            quantity = "resonance_frequency_ghz"
    except (ValueError, OSError) as exc:
        return _failed(prepared, f"Could not extract resonance from {s2p.name}: {exc}")

    target = target_frequency_ghz
    if quantity == "characteristic_impedance_ohm":
        target = _prepared_target(prepared, "impedance_ohm") or _prepared_target(prepared, "z0_ohm")
    comparison = _compare(value, target, tolerance_pct, quantity)
    return SimulationResult(
        status="executed",
        solver=f"{prepared.solver}+scikit-rf",
        readiness_level=4 if comparison else 3,
        reason=f"Extracted {quantity} from solver-owned {s2p.name}.",
        output_dir=prepared.output_dir,
        artifacts={**artifacts, "touchstone": str(s2p), "result": str(s2p)},
        extracted_quantities=extracted,
        target_comparison=comparison,
        warnings=prepared.warnings,
        command=completed.command if completed is not None else (),
        return_code=completed.returncode if completed is not None else 0,
        runtime_seconds=completed.runtime_seconds if completed is not None else None,
        solver_version="openEMS via Octave frontend",
    )


def _extract_openems_cpw_metrics(
    path: Path, frequency_ghz: float | None
) -> dict[str, float]:
    import csv

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    if not rows:
        raise ValueError("openEMS metrics CSV has no rows")
    target = frequency_ghz * 1e9 if frequency_ghz is not None else float(
        rows[len(rows) // 2]["frequency_hz"]
    )
    row = min(rows, key=lambda item: abs(float(item["frequency_hz"]) - target))
    z0 = complex(float(row["z0_real"]), float(row["z0_imag"]))
    return {
        "characteristic_impedance_ohm": abs(z0),
        "characteristic_impedance_real_ohm": z0.real,
        "characteristic_impedance_imag_ohm": z0.imag,
    }


def _prepared_payload(prepared: SimulationResult) -> dict[str, Any]:
    model = prepared.artifacts.get("model")
    if model is None:
        return {}
    try:
        import json

        return cast(dict[str, Any], json.loads(Path(model).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def _prepared_component(prepared: SimulationResult) -> str:
    return str(_prepared_payload(prepared).get("component", "QuarterWaveResonator"))


def _prepared_target(prepared: SimulationResult, name: str) -> float | None:
    target = _prepared_payload(prepared).get("target", {})
    value = target.get(name) if isinstance(target, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def extract_cpw_from_touchstone(
    path: str | Path, frequency_ghz: float | None = None
) -> dict[str, float]:
    """Estimate a through-line CPW impedance from its complex S11/S21.

    This uses the symmetric reciprocal two-port conversion
    ``Z0 = Zref*sqrt(((1+S11)^2-S21^2)/((1-S11)^2-S21^2))`` at the requested
    frequency (or sweep centre). The output is a solver-derived port impedance,
    not the analytical CPW formula.
    """
    from textlayout.simulation.sparameters import (
        compute_return_loss_db,
        estimate_z0_from_network,
        read_sparameters,
    )

    data = read_sparameters(path)
    if not data.frequencies_hz:
        raise ValueError("no frequency points")
    desired = (
        frequency_ghz * 1e9
        if frequency_ghz is not None
        else data.frequencies_hz[len(data.frequencies_hz) // 2]
    )
    index = min(
        range(len(data.frequencies_hz)),
        key=lambda i: abs(data.frequencies_hz[i] - desired),
    )
    z0 = estimate_z0_from_network(path, desired)
    return {
        "characteristic_impedance_ohm": z0,
        "sample_frequency_ghz": data.frequencies_hz[index] / 1e9,
        "s11_magnitude": float(abs(data.s11[index])),
        "return_loss_db": compute_return_loss_db(data.s11[index]),
    }


def _read_touchstone_complex(path: str | Path) -> tuple[list[float], list[complex], list[complex]]:
    """Read two-port S11/S21 using scikit-rf, with an RI fallback."""
    try:
        import skrf  # type: ignore

        network = skrf.Network(str(path))
        if network.nports < 2:
            raise ValueError("CPW extraction requires a two-port Touchstone file")
        return (
            [float(value) for value in network.f],
            [complex(value) for value in network.s[:, 0, 0]],
            [complex(value) for value in network.s[:, 1, 0]],
        )
    except ImportError:
        return _read_touchstone_ri_fallback(Path(path))


def _read_touchstone_ri_fallback(path: Path) -> tuple[list[float], list[complex], list[complex]]:
    scale = 1.0
    fmt = "ri"
    freqs: list[float] = []
    s11: list[complex] = []
    s21: list[complex] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("#"):
            tokens = line.lower().split()
            scale = (
                1e9
                if "ghz" in tokens
                else 1e6
                if "mhz" in tokens
                else 1e3
                if "khz" in tokens
                else 1.0
            )
            fmt = next((token for token in tokens if token in {"ri", "ma", "db"}), "ri")
            continue
        values = [float(token) for token in line.split()]
        if len(values) < 9:
            continue
        freqs.append(values[0] * scale)
        s11.append(_complex_pair(values[1], values[2], fmt))
        s21.append(_complex_pair(values[3], values[4], fmt))
    return freqs, s11, s21


def _complex_pair(first: float, second: float, fmt: str) -> complex:
    if fmt == "ri":
        return complex(first, second)
    magnitude = 10 ** (first / 20.0) if fmt == "db" else first
    angle = math.radians(second)
    return magnitude * complex(math.cos(angle), math.sin(angle))


def _find_touchstone(prepared: SimulationResult, explicit: str | Path | None) -> Path | None:
    if explicit is not None:
        path = Path(explicit)
        return path if path.is_file() and path.stat().st_size > 0 else None
    if prepared.output_dir is None:
        return None
    for pattern in ("*.s2p", "*.s1p", "*.snp"):
        for candidate in sorted(Path(prepared.output_dir).glob(pattern)):
            if candidate.stat().st_size > 0:
                return candidate
    return None


def extract_resonance_from_touchstone(path: str | Path) -> float:
    """Resonance frequency (GHz) from |S21| using scikit-rf when available.

    For a hanger/notch resonator the resonance is the |S21| minimum; this
    returns whichever of the global |S21| extrema is most pronounced, which
    covers both notch and peak topologies. Falls back to a minimal Touchstone
    parser if scikit-rf is not installed.
    """
    return extract_resonance_metrics_from_touchstone(path)["resonance_frequency_ghz"]


def extract_resonance_metrics_from_touchstone(path: str | Path) -> dict[str, float]:
    """Extract resonance and a best-effort loaded-Q estimate from Touchstone data."""
    from textlayout.simulation.sparameters import find_resonance_frequency, read_sparameters

    data = read_sparameters(path)
    freqs_hz = list(data.frequencies_hz)
    s21_mag = [abs(value) for value in data.s21]
    if not freqs_hz:
        raise ValueError("no frequency points")
    mean = sum(s21_mag) / len(s21_mag)
    # Pick the extremum with the larger deviation from the mean (notch or peak).
    i_min = min(range(len(s21_mag)), key=lambda i: s21_mag[i])
    i_max = max(range(len(s21_mag)), key=lambda i: s21_mag[i])
    resonance_hz = find_resonance_frequency(path)
    idx = min(range(len(freqs_hz)), key=lambda i: abs(freqs_hz[i] - resonance_hz))
    result = {
        "resonance_frequency_ghz": freqs_hz[idx] / 1e9,
        "s21_magnitude_at_resonance": s21_mag[idx],
    }
    if len(freqs_hz) >= 3:
        is_notch = idx == i_min
        baseline = max(s21_mag[0], s21_mag[-1]) if is_notch else min(
            s21_mag[0], s21_mag[-1]
        )
        threshold_power = (
            (baseline * baseline + s21_mag[idx] * s21_mag[idx]) / 2.0
            if is_notch
            else s21_mag[idx] * s21_mag[idx] / 2.0
        )
        crossings = [
            i
            for i in range(len(s21_mag) - 1)
            if (s21_mag[i] ** 2 - threshold_power)
            * (s21_mag[i + 1] ** 2 - threshold_power)
            <= 0
        ]
        left = [i for i in crossings if i < idx]
        right = [i for i in crossings if i >= idx]
        if left and right:
            bandwidth_hz = freqs_hz[right[0] + 1] - freqs_hz[left[-1]]
            if bandwidth_hz > 0:
                result["loaded_q_estimate"] = freqs_hz[idx] / bandwidth_hz
    return result


def _read_touchstone_s21(path: str | Path) -> tuple[list[float], list[float]]:
    path = Path(path)
    try:
        import skrf

        network = skrf.Network(str(path))
        freqs = [float(f) for f in network.f]
        # Two-port -> S21; one-port -> S11.
        s = network.s[:, 1, 0] if network.nports >= 2 else network.s[:, 0, 0]
        return freqs, [float(abs(value)) for value in s]
    except ImportError:
        return _read_touchstone_s21_fallback(path)


def _read_touchstone_s21_fallback(path: Path) -> tuple[list[float], list[float]]:
    """Minimal magnitude/angle Touchstone reader (no scikit-rf required)."""
    unit_scale = 1e9  # default GHz
    fmt = "ma"
    freqs: list[float] = []
    mags: list[float] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("#"):
            tokens = line.lower().split()
            if "hz" in tokens:
                unit_scale = 1.0
            elif "khz" in tokens:
                unit_scale = 1e3
            elif "mhz" in tokens:
                unit_scale = 1e6
            elif "ghz" in tokens:
                unit_scale = 1e9
            for token in tokens:
                if token in {"ma", "db", "ri"}:
                    fmt = token
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        freq = float(parts[0]) * unit_scale
        # 2-port: freq S11(2) S21(2) S12(2) S22(2); 1-port: freq S11(2).
        col = 3 if len(parts) >= 5 else 1  # S21 first value when present
        first = float(parts[col])
        if fmt == "db":
            magnitude = 10 ** (first / 20.0)
        elif fmt == "ri":
            imag = float(parts[col + 1])
            magnitude = math.hypot(first, imag)
        else:  # ma
            magnitude = first
        freqs.append(freq)
        mags.append(magnitude)
    return freqs, mags
