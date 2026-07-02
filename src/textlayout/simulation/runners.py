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
from typing import Any

from textlayout.simulation.models import SimulationResult


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
        completed = subprocess.run(
            [solver, input_path.name],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _failed(prepared, f"FastHenry execution failed: {exc}")

    (work / "fasthenry.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    zc = work / "Zc.mat"
    if completed.returncode != 0 or not zc.is_file():
        return _failed(
            prepared,
            f"FastHenry exited {completed.returncode} without a Zc.mat output.",
            solver_stdout=work / "fasthenry.stdout.txt",
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
_OPENEMS_NAMES = ("openEMS", "openEMS.exe", "openems")


def run_openems(
    prepared: SimulationResult,
    *,
    target_frequency_ghz: float | None = None,
    tolerance_pct: float = 5.0,
    touchstone: str | Path | None = None,
    executable: str | None = None,
) -> SimulationResult:
    """Post-process an openEMS Touchstone result, when one exists.

    The textlayout openEMS adapter currently prepares a solver-input manifest,
    not a runnable CSXCAD model (see the TODO note in the returned ``reason``).
    This runner therefore does the honest, useful half: if a Touchstone file is
    available (produced by a manual openEMS run or the legacy
    ``text_to_gds.openems_runner``), it extracts the resonance with scikit-rf and
    compares it against the target. Otherwise it reports the missing piece
    without faking a result.
    """
    s2p = _find_touchstone(prepared, touchstone)
    if s2p is None:
        solver = find_executable(_OPENEMS_NAMES, executable)
        reason = (
            "No Touchstone output found. Generating a runnable CSXCAD model from the "
            "prepared manifest is not yet implemented in textlayout "
            "(TODO: port text_to_gds.openems_runner). "
            + ("openEMS is installed; " if solver else "openEMS is not installed; ")
            + "run it externally and pass touchstone=<path> to extract and compare."
        )
        return SimulationResult(
            status="skipped" if solver is None else "failed",
            solver=prepared.solver,
            readiness_level=prepared.readiness_level,
            reason=reason,
            output_dir=prepared.output_dir,
            artifacts=dict(prepared.artifacts),
            warnings=prepared.warnings,
        )
    try:
        resonance_ghz = extract_resonance_from_touchstone(s2p)
    except (ValueError, OSError) as exc:
        return _failed(prepared, f"Could not extract resonance from {s2p.name}: {exc}")

    extracted = {"resonance_frequency_ghz": resonance_ghz}
    comparison = _compare(
        resonance_ghz, target_frequency_ghz, tolerance_pct, "resonance_frequency_ghz"
    )
    return SimulationResult(
        status="executed",
        solver=f"{prepared.solver}+scikit-rf",
        readiness_level=4 if comparison else 3,
        reason=f"Extracted resonance from {s2p.name} via scikit-rf.",
        output_dir=prepared.output_dir,
        artifacts={**prepared.artifacts, "touchstone": str(s2p), "result": str(s2p)},
        extracted_quantities=extracted,
        target_comparison=comparison,
        warnings=prepared.warnings,
    )


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
        import skrf  # type: ignore

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


def _compare(
    value: float, target: float | None, tolerance_pct: float, key: str
) -> dict[str, Any] | None:
    if target is None:
        return None
    error_pct = 100.0 * (value - target) / target if target else float("inf")
    return {
        "quantity": key,
        "extracted": value,
        "target": target,
        "error_pct": round(error_pct, 3),
        "tolerance_pct": tolerance_pct,
        "within_tolerance": abs(error_pct) <= tolerance_pct,
    }
