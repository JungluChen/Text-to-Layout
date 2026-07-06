"""Touchstone and CSV S-parameter parsing with an optional scikit-rf backend."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SParameterData:
    frequencies_hz: tuple[float, ...]
    s11: tuple[complex, ...]
    s21: tuple[complex, ...]
    reference_ohm: float = 50.0


def read_sparameters(path: str | Path) -> SParameterData:
    """Parse S-parameters and reject non-finite data.

    A Touchstone full of NaN/Inf is what a solver writes when its ports never
    injected energy (0/0 in the S computation). Accepting it silently once
    produced a fake "resonance at 3.0 GHz" claim from an all-NaN file — the
    parser is the honesty gate, so it raises instead of returning garbage.
    """
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return _validated(_read_csv(source), source)
    try:
        import skrf  # type: ignore[import-not-found]

        network = skrf.Network(str(source))
        s11 = tuple(complex(value) for value in network.s[:, 0, 0])
        s21 = (
            tuple(complex(value) for value in network.s[:, 1, 0])
            if network.nports >= 2
            else tuple(0j for _ in s11)
        )
        reference = float(network.z0[0, 0].real) if network.z0.size else 50.0
        data = SParameterData(
            tuple(float(value) for value in network.f), s11, s21, reference
        )
    except ImportError:
        data = _read_touchstone(source)
    return _validated(data, source)


def _validated(data: SParameterData, source: Path) -> SParameterData:
    def _finite(value: complex) -> bool:
        return math.isfinite(value.real) and math.isfinite(value.imag)

    bad = sum(
        1
        for freq, a, b in zip(data.frequencies_hz, data.s11, data.s21)
        if not (math.isfinite(freq) and _finite(a) and _finite(b))
    )
    if bad:
        raise ValueError(
            f"{source.name}: {bad}/{len(data.frequencies_hz)} S-parameter samples "
            "are non-finite (NaN/Inf) — the solver produced no usable output "
            "(typically zero injected port energy); refusing to extract numbers "
            "from it"
        )
    return data


def extract_s11_at_frequency(path: str | Path, frequency_hz: float) -> complex:
    data = read_sparameters(path)
    return data.s11[_nearest_index(data.frequencies_hz, frequency_hz)]


def extract_s21_at_frequency(path: str | Path, frequency_hz: float) -> complex:
    data = read_sparameters(path)
    return data.s21[_nearest_index(data.frequencies_hz, frequency_hz)]


def estimate_z0_from_network(path: str | Path, frequency_hz: float) -> float:
    """Estimate uniform symmetric-line Z0 from solver-derived S11/S21."""
    data = read_sparameters(path)
    index = _nearest_index(data.frequencies_hz, frequency_hz)
    s11 = data.s11[index]
    s21 = data.s21[index]
    numerator = (1 + s11) ** 2 - s21**2
    denominator = (1 - s11) ** 2 - s21**2
    if abs(denominator) < 1e-15:
        raise ValueError("singular S-to-Z conversion")
    return float(abs(data.reference_ohm * complex(numerator / denominator) ** 0.5))


#: A resonance claimed within this many bins of the sweep edge is rejected:
#: monotonic (resonance-free) data always has its extremum at an edge, so an
#: edge extremum is evidence of NO resonance in band, not of one at f_start.
_EDGE_GUARD_BINS = 2


def find_resonance_frequency(path: str | Path, *, parameter: str = "s21") -> float:
    """Return the strongest dip/peak frequency in Hz for S21 or S11.

    Raises ``ValueError`` when the strongest deviation sits at the sweep edge
    — that is what monotonic, resonance-free data looks like, and reporting
    the sweep boundary as "the resonance" is a fake claim (it once produced
    "resonance = 3.0 GHz" purely because the sweep started at 3.0 GHz).
    """
    data = read_sparameters(path)
    values = data.s21 if parameter.casefold() == "s21" else data.s11
    magnitudes = [abs(value) for value in values]
    if not magnitudes:
        raise ValueError("no S-parameter samples")
    mean = sum(magnitudes) / len(magnitudes)
    low = min(range(len(magnitudes)), key=magnitudes.__getitem__)
    high = max(range(len(magnitudes)), key=magnitudes.__getitem__)

    def _interior(index: int) -> bool:
        if len(magnitudes) <= 2 * _EDGE_GUARD_BINS:
            return True
        return _EDGE_GUARD_BINS <= index < len(magnitudes) - _EDGE_GUARD_BINS

    # Rank notch vs peak by deviation from the mean, but an edge extremum is
    # never a resonance — a monotonic baseline ramp puts its extremum at the
    # edge by construction. Prefer whichever candidate is interior.
    candidates = sorted(
        (low, high),
        key=lambda i: (mean - magnitudes[i]) if i == low else (magnitudes[i] - mean),
        reverse=True,
    )
    for index in candidates:
        if _interior(index):
            return data.frequencies_hz[index]
    f_lo = data.frequencies_hz[0] / 1e9
    f_hi = data.frequencies_hz[-1] / 1e9
    raise ValueError(
        f"no resonance found in the {f_lo:g}-{f_hi:g} GHz sweep: every "
        f"|{parameter.upper()}| extremum sits at the sweep edge, which is what "
        "monotonic, resonance-free data looks like — widen the sweep or fix "
        "the model instead of reporting the edge frequency"
    )


def compute_return_loss_db(s11: complex) -> float:
    return float(-20.0 * math.log10(max(abs(s11), 1e-15)))


def _nearest_index(frequencies: tuple[float, ...], target: float) -> int:
    if not frequencies:
        raise ValueError("no frequency samples")
    return min(range(len(frequencies)), key=lambda index: abs(frequencies[index] - target))


def _read_csv(path: Path) -> SParameterData:
    frequencies: list[float] = []
    s11: list[complex] = []
    s21: list[complex] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            frequencies.append(float(row["frequency_hz"]))
            s11.append(complex(float(row["s11_real"]), float(row["s11_imag"])))
            s21.append(complex(float(row.get("s21_real", 0.0)), float(row.get("s21_imag", 0.0))))
    return SParameterData(tuple(frequencies), tuple(s11), tuple(s21))


def _read_touchstone(path: Path) -> SParameterData:
    scale = 1.0
    form = "ri"
    reference = 50.0
    frequencies: list[float] = []
    s11: list[complex] = []
    s21: list[complex] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("#"):
            tokens = line.casefold().split()
            scale = 1e9 if "ghz" in tokens else 1e6 if "mhz" in tokens else 1e3 if "khz" in tokens else 1.0
            form = next((token for token in tokens if token in {"ri", "ma", "db"}), "ri")
            if "r" in tokens:
                reference = float(tokens[tokens.index("r") + 1])
            continue
        values = [float(token) for token in line.split()]
        if len(values) < 3:
            continue
        frequencies.append(values[0] * scale)
        s11.append(_pair(values[1], values[2], form))
        s21.append(_pair(values[3], values[4], form) if len(values) >= 5 else 0j)
    return SParameterData(tuple(frequencies), tuple(s11), tuple(s21), reference)


def _pair(first: float, second: float, form: str) -> complex:
    if form == "ri":
        return complex(first, second)
    magnitude = 10 ** (first / 20.0) if form == "db" else first
    angle = math.radians(second)
    return magnitude * complex(math.cos(angle), math.sin(angle))
