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
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return _read_csv(source)
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
        return SParameterData(
            tuple(float(value) for value in network.f), s11, s21, reference
        )
    except ImportError:
        return _read_touchstone(source)


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


def find_resonance_frequency(path: str | Path, *, parameter: str = "s21") -> float:
    """Return the strongest dip/peak frequency in Hz for S21 or S11."""
    data = read_sparameters(path)
    values = data.s21 if parameter.casefold() == "s21" else data.s11
    magnitudes = [abs(value) for value in values]
    if not magnitudes:
        raise ValueError("no S-parameter samples")
    mean = sum(magnitudes) / len(magnitudes)
    low = min(range(len(magnitudes)), key=magnitudes.__getitem__)
    high = max(range(len(magnitudes)), key=magnitudes.__getitem__)
    index = low if mean - magnitudes[low] >= magnitudes[high] - mean else high
    return data.frequencies_hz[index]


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
