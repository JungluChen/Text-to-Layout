"""Touchstone file validation and feature analysis for solver-produced RF traces.

Two-layer validation:
  validate_touchstone(path) — file-level: scikit-rf load + passivity + reciprocity.
  analyze_rf_trace(...)     — trace-level: resonance features, flat-response detection.

validate_touchstone is the gatekeeper for all Touchstone evidence.  It must pass
before any plotting or cross-check occurs.  If scikit-rf is unavailable it falls back
to the manual parser in rf.py; the same passivity and reciprocity checks apply.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import pstdev
from typing import Any

SCHEMA = "text-to-gds.rf-validation.v1"


def _failed_validation(reason: str, *, report_path: Path | None = None) -> dict[str, Any]:
    result = {"schema": SCHEMA, "status": "failed", "reason": reason}
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["report_path"] = str(report_path)
    return result


def validate_touchstone(
    path: str | Path,
    *,
    report_path: str | Path | None = None,
    plot_path: str | Path | None = None,
    passivity_tolerance: float = 1e-6,
    reciprocity_tolerance: float = 1e-3,
) -> dict[str, Any]:
    """Validate a Touchstone .s2p file and optionally write a report and plot.

    Checks (in order):
      1. File exists.
      2. File can be loaded (scikit-rf preferred; manual parser fallback).
      3. Network has exactly 2 ports.
      4. Frequency axis is valid (monotone, positive, finite).
      5. S-matrix values are all finite.
      6. Passivity: max_singular_value(S)^2 <= 1 + tolerance.
      7. Reciprocity: |S21 - S12| <= reciprocity_tolerance (passive networks only).

    Returns a result dict with status='ok' or status='failed' plus validation details.
    """
    source = Path(path)
    rp = Path(report_path) if report_path is not None else None

    if not source.is_file():
        return _failed_validation(f"Touchstone file not found: {source}", report_path=rp)

    # ------------------------------------------------------------------ #
    # Attempt scikit-rf load; fall back to manual parser.
    # ------------------------------------------------------------------ #
    use_skrf = False
    frequencies_hz: list[float] = []
    matrices: list[Any] = []

    try:
        import skrf  # type: ignore[import]
        import numpy as np

        nw = skrf.Network(str(source))
        if nw.number_of_ports != 2:
            return _failed_validation(
                f"expected 2-port network, got {nw.number_of_ports} ports", report_path=rp
            )
        frequencies_hz = list(float(f) for f in nw.f)
        matrices = [nw.s[i] for i in range(len(frequencies_hz))]
        use_skrf = True
    except ImportError:
        # Fall back to the manual Touchstone parser in rf.py.
        from textlayout._legacy.rf import parse_touchstone
        try:
            parsed = parse_touchstone(source)
        except (OSError, ValueError) as e:
            return _failed_validation(f"invalid Touchstone file: {e}", report_path=rp)
        frequencies_hz = parsed["frequencies_hz"]
        matrices = parsed["matrices"]
    except Exception as e:  # noqa: BLE001
        return _failed_validation(f"scikit-rf failed to load file: {e}", report_path=rp)

    import numpy as np

    # ------------------------------------------------------------------ #
    # Frequency axis checks.
    # ------------------------------------------------------------------ #
    if len(frequencies_hz) < 2:
        return _failed_validation("frequency axis has fewer than 2 points", report_path=rp)
    if any(not math.isfinite(f) or f <= 0.0 for f in frequencies_hz):
        return _failed_validation("frequency axis contains non-positive or non-finite values", report_path=rp)
    if frequencies_hz != sorted(frequencies_hz):
        return _failed_validation("frequency axis is not monotonically increasing", report_path=rp)

    # ------------------------------------------------------------------ #
    # S-matrix finiteness.
    # ------------------------------------------------------------------ #
    for i, mat in enumerate(matrices):
        m = np.asarray(mat)
        if not np.all(np.isfinite(m)):
            return _failed_validation(
                f"S-matrix at frequency index {i} contains non-finite values", report_path=rp
            )

    # ------------------------------------------------------------------ #
    # Passivity: max singular value^2 <= 1 + tolerance.
    # ------------------------------------------------------------------ #
    max_power = 0.0
    for mat in matrices:
        sv = np.linalg.svd(np.asarray(mat, dtype=complex), compute_uv=False)
        max_power = max(max_power, float(sv[0] ** 2))

    if max_power > 1.0 + passivity_tolerance:
        return _failed_validation(
            f"Touchstone data violates passive power conservation "
            f"(max singular value^2 = {max_power:.6g} > 1 + {passivity_tolerance})",
            report_path=rp,
        )

    # ------------------------------------------------------------------ #
    # Reciprocity: |S21 - S12| <= tolerance.
    # ------------------------------------------------------------------ #
    max_recip_error = 0.0
    for mat in matrices:
        m = np.asarray(mat, dtype=complex)
        max_recip_error = max(max_recip_error, float(abs(m[1, 0] - m[0, 1])))

    if max_recip_error > reciprocity_tolerance:
        return _failed_validation(
            f"Touchstone data violates reciprocity "
            f"(max |S21-S12| = {max_recip_error:.6g} > {reciprocity_tolerance})",
            report_path=rp,
        )

    # ------------------------------------------------------------------ #
    # Optional plot.
    # ------------------------------------------------------------------ #
    plot_written: str | None = None
    if plot_path is not None:
        try:
            _write_validation_plot(frequencies_hz, matrices, Path(plot_path))
            plot_written = str(plot_path)
        except Exception:  # noqa: BLE001
            plot_written = None

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "ok",
        "source": str(source),
        "loader": "scikit-rf" if use_skrf else "manual_parser",
        "frequency_points": len(frequencies_hz),
        "frequency_range_ghz": [frequencies_hz[0] / 1e9, frequencies_hz[-1] / 1e9],
        "passivity": True,
        "reciprocity": True,
        "max_output_power_ratio": max_power,
        "max_reciprocity_error": max_recip_error,
        "passivity_tolerance": passivity_tolerance,
        "reciprocity_tolerance": reciprocity_tolerance,
        "plot_path": plot_written,
    }
    if rp is not None:
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["report_path"] = str(rp)
    return result


def _write_validation_plot(
    frequencies_hz: list[float],
    matrices: list[Any],
    plot_path: Path,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    x = [f / 1e9 for f in frequencies_hz]

    def db(v: complex) -> float:
        return 20.0 * math.log10(max(abs(v), 1e-300))

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8.4, 5.2), constrained_layout=True)
    for row, col, label in ((0, 0, "S11"), (1, 0, "S21"), (0, 1, "S12"), (1, 1, "S22")):
        m = np.asarray(matrices[0])
        if m.shape == (2, 2):
            ax.plot(x, [db(np.asarray(mat)[row, col]) for mat in matrices], label=label)
    ax.set(xlabel="Frequency (GHz)", ylabel="Magnitude (dB)",
           title="Validated solver Touchstone S-parameters")
    ax.legend(loc="best")
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def analyze_rf_trace(
    frequencies_ghz: list[float],
    s_parameters_db: dict[str, list[float]],
    *,
    active: bool,
    require_resonance: bool = False,
    flat_tolerance_db: float = 0.05,
    minimum_feature_depth_db: float = 1.0,
) -> dict[str, Any]:
    errors: list[str] = []
    if len(frequencies_ghz) < 3:
        errors.append("RF trace requires at least three frequency points")
    arrays: dict[str, list[float]] = {}
    for key in ("s11_db", "s21_db", "s12_db", "s22_db"):
        values = s_parameters_db.get(key)
        if isinstance(values, list) and len(values) == len(frequencies_ghz):
            arrays[key] = [float(value) for value in values]
    if "s21_db" not in arrays:
        errors.append("S21 trace is missing or length-mismatched")
        return {
            "schema": "text-to-gds.rf-feature-check.v1",
            "status": "failed",
            "errors": errors,
            "features": {},
        }

    s21 = arrays["s21_db"]
    variation = max(s21) - min(s21)
    flat = pstdev(s21) <= flat_tolerance_db
    if flat:
        errors.append("S21 response is flat")
    if not active and max(s21) > 1e-3:
        errors.append("passive network has positive S21 gain")

    peak_index = max(range(len(s21)), key=s21.__getitem__)
    notch_index = min(range(len(s21)), key=s21.__getitem__)
    baseline = (s21[0] + s21[-1]) / 2.0
    peak_prominence = s21[peak_index] - baseline
    notch_depth = baseline - s21[notch_index]
    resonance_kind = "peak" if peak_prominence >= notch_depth else "notch"
    feature_depth = max(peak_prominence, notch_depth)
    feature_index = peak_index if resonance_kind == "peak" else notch_index
    if require_resonance and feature_depth < minimum_feature_depth_db:
        errors.append("no resonance feature detected")

    bandwidth_mhz = None
    if active and peak_prominence >= minimum_feature_depth_db:
        threshold = s21[peak_index] - 3.0
        selected = [index for index, value in enumerate(s21) if value >= threshold]
        if selected:
            bandwidth_mhz = (
                frequencies_ghz[max(selected)] - frequencies_ghz[min(selected)]
            ) * 1000.0
    elif not active and notch_depth >= minimum_feature_depth_db:
        threshold = s21[notch_index] + 3.0
        selected = [index for index, value in enumerate(s21) if value <= threshold]
        if selected:
            bandwidth_mhz = (
                frequencies_ghz[max(selected)] - frequencies_ghz[min(selected)]
            ) * 1000.0

    finite = all(math.isfinite(value) for values in arrays.values() for value in values)
    if not finite:
        errors.append("RF trace contains non-finite values")
    return {
        "schema": "text-to-gds.rf-feature-check.v1",
        "status": "ok" if not errors else "failed",
        "errors": errors,
        "features": {
            "flat": flat,
            "variation_db": variation,
            "resonance_kind": resonance_kind,
            "resonance_frequency_ghz": frequencies_ghz[feature_index],
            "feature_depth_db": feature_depth,
            "bandwidth_3db_mhz": bandwidth_mhz,
            "peak_s21_db": s21[peak_index],
        },
    }
