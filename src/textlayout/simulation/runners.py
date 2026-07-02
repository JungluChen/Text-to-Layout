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
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

from textlayout.simulation.models import SimulationResult, target_comparison as _compare
from textlayout.solvers.base import run_subprocess


def find_executable(names: tuple[str, ...], explicit: str | None = None) -> str | None:
    """Resolve a solver binary from an explicit path or ``PATH``."""
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return str(path)
        return shutil.which(explicit)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


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
    tolerance_pct: float = 20.0,
    executable: str | None = None,
    timeout_seconds: int = 600,
) -> SimulationResult:
    """Execute FastHenry on a prepared ``.inp`` and extract the inductance."""
    input_path = Path(prepared.artifacts.get("input", ""))
    if not input_path.is_file():
        return _failed(prepared, "No FastHenry .inp input was prepared.")
    solver = find_executable(_FASTHENRY_NAMES, executable)
    if solver is None:
        return _skipped(prepared, _FASTHENRY_NAMES)

    work = input_path.parent
    try:
        completed = run_subprocess(
            [solver, input_path.name],
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
        artifacts={**prepared.artifacts, "zc_matrix": str(zc), "result": str(zc)},
        extracted_quantities=extracted,
        target_comparison=comparison,
        warnings=prepared.warnings,
        command=(Path(solver).name, input_path.name),
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
        solver = find_executable(_OPENEMS_NAMES, executable)
        if solver is None:
            return _skipped(prepared, _OPENEMS_NAMES)
        driver = Path(prepared.artifacts.get("driver", ""))
        if not driver.is_file():
            return _failed(prepared, "No runnable openEMS Octave driver was prepared.")
        try:
            completed = run_subprocess(
                [solver, "--quiet", "--no-gui", driver.name],
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
            quantity = "characteristic_impedance_ohm"
            value = extracted[quantity]
        else:
            value = extract_resonance_from_touchstone(s2p)
            extracted = {"resonance_frequency_ghz": value}
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
    )


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
    freqs, s11, s21 = _read_touchstone_complex(path)
    if not freqs:
        raise ValueError("no frequency points")
    desired = frequency_ghz * 1e9 if frequency_ghz is not None else freqs[len(freqs) // 2]
    index = min(range(len(freqs)), key=lambda i: abs(freqs[i] - desired))
    numerator = (1 + s11[index]) ** 2 - s21[index] ** 2
    denominator = (1 - s11[index]) ** 2 - s21[index] ** 2
    if abs(denominator) < 1e-15:
        raise ValueError("singular S-to-Z conversion")
    z0 = 50.0 * complex(numerator / denominator) ** 0.5
    return {
        "characteristic_impedance_ohm": float(abs(z0)),
        "sample_frequency_ghz": freqs[index] / 1e9,
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
    freqs_hz, s21_mag = _read_touchstone_s21(path)
    if not freqs_hz:
        raise ValueError("no frequency points")
    mean = sum(s21_mag) / len(s21_mag)
    # Pick the extremum with the larger deviation from the mean (notch or peak).
    i_min = min(range(len(s21_mag)), key=lambda i: s21_mag[i])
    i_max = max(range(len(s21_mag)), key=lambda i: s21_mag[i])
    idx = i_min if (mean - s21_mag[i_min]) >= (s21_mag[i_max] - mean) else i_max
    return freqs_hz[idx] / 1e9


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
