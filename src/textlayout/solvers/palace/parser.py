"""Strict Palace output parsing and solver-field overlap calculations."""

from __future__ import annotations

import csv
import base64
import json
import math
import re
import struct
import zlib
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np
import numpy.typing as npt

from textlayout.solvers.palace.models import Eigenmode, ModeFieldData, PalaceOutputError

_EIG_INDEX = re.compile(r"^\s*m\s*$", re.IGNORECASE)
_EIG_REAL = re.compile(r"re\s*\{?\s*f\s*\}?.*ghz", re.IGNORECASE)
_EIG_IMAG = re.compile(r"im\s*\{?\s*f\s*\}?.*ghz", re.IGNORECASE)
_EIG_Q = re.compile(r"^\s*q\s*$", re.IGNORECASE)
_EIG_BACKWARD = re.compile(r"error.*bkwd", re.IGNORECASE)
_EIG_ABSOLUTE = re.compile(r"error.*abs", re.IGNORECASE)
_DOF_PATTERNS = (
    re.compile(r"(?:Nedelec|H\(curl\)|ND).*?(?:dof|unknown|size)[^0-9]*([0-9][0-9,]*)", re.I),
    re.compile(r"(?:degrees?\s+of\s+freedom|dofs?)[^0-9]*([0-9][0-9,]*)", re.I),
)


def _column(header: list[str], pattern: re.Pattern[str], what: str, source: Path) -> int:
    for index, name in enumerate(header):
        if pattern.search(name.strip()):
            return index
    raise PalaceOutputError(f"{source}: no {what} column in header {header!r}")


def _optional_column(header: list[str], pattern: re.Pattern[str]) -> int | None:
    for index, name in enumerate(header):
        if pattern.search(name.strip()):
            return index
    return None


def _finite(cell: str | float | int, source: Path, what: str) -> float:
    try:
        value = float(cell)
    except (TypeError, ValueError) as exc:
        raise PalaceOutputError(f"{source}: {what} is not a number: {cell!r}") from exc
    if not math.isfinite(value):
        raise PalaceOutputError(f"{source}: {what} is not finite: {value!r}")
    return value


def parse_eigenmodes(eig_csv: Path) -> list[Eigenmode]:
    if not eig_csv.is_file():
        raise PalaceOutputError(f"missing Palace eigenvalue output: {eig_csv}")
    with eig_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise PalaceOutputError(f"{eig_csv}: no eigenvalue rows")
    header = rows[0]
    index_column = _column(header, _EIG_INDEX, "mode index", eig_csv)
    real_column = _column(header, _EIG_REAL, "Re{f} (GHz)", eig_csv)
    imag_column = _optional_column(header, _EIG_IMAG)
    quality_column = _optional_column(header, _EIG_Q)
    backward_column = _optional_column(header, _EIG_BACKWARD)
    absolute_column = _optional_column(header, _EIG_ABSOLUTE)

    modes: list[Eigenmode] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        try:
            index = int(float(row[index_column]))
            frequency = _finite(row[real_column], eig_csv, "Re{f}")
            modes.append(
                Eigenmode(
                    index=index,
                    frequency_ghz=frequency,
                    frequency_imag_ghz=(
                        _finite(row[imag_column], eig_csv, "Im{f}")
                        if imag_column is not None
                        else None
                    ),
                    quality_factor=(
                        _finite(row[quality_column], eig_csv, "Q")
                        if quality_column is not None
                        else None
                    ),
                    backward_error=(
                        _finite(row[backward_column], eig_csv, "backward error")
                        if backward_column is not None
                        else None
                    ),
                    absolute_error=(
                        _finite(row[absolute_column], eig_csv, "absolute error")
                        if absolute_column is not None
                        else None
                    ),
                )
            )
        except IndexError as exc:
            raise PalaceOutputError(f"{eig_csv}: short eigenvalue row {row!r}") from exc
    if not modes:
        raise PalaceOutputError(f"{eig_csv}: header present but no eigenvalues")
    return modes


def parse_domain_energy(domain_csv: Path, *, mode: int = 1) -> dict[int, float]:
    if not domain_csv.is_file():
        raise PalaceOutputError(f"missing Palace domain energy output: {domain_csv}")
    with domain_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise PalaceOutputError(f"{domain_csv}: no domain energy rows")
    header = [cell.strip() for cell in rows[0]]
    mode_column = _column(header, _EIG_INDEX, "mode index", domain_csv)
    selected: list[str] | None = None
    available: list[int] = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        index = int(float(row[mode_column]))
        available.append(index)
        if index == mode:
            selected = row
    if selected is None:
        raise PalaceOutputError(
            f"{domain_csv}: no energy row for mode {mode}; the file carries modes {available}"
        )
    energies: dict[int, float] = {}
    for index, name in enumerate(header):
        match = re.search(r"E_elec\s*\[\s*(\d+)\s*\]", name, re.IGNORECASE)
        if match:
            energies[int(match.group(1))] = _finite(selected[index], domain_csv, name)
    if not energies:
        raise PalaceOutputError(
            f"{domain_csv}: no per-domain E_elec columns; enable "
            "Domains.Postprocessing.Energy in the Palace configuration"
        )
    return energies


def _field_file(output_dir: Path, mode: int) -> Path | None:
    token = f"Cycle{mode:06d}".lower()
    candidates = sorted(output_dir.rglob("*.pvtu"))
    matched = [path for path in candidates if token in str(path).lower()]
    selected = matched[0] if matched else (candidates[0] if len(candidates) == 1 else None)
    if selected is None:
        return None
    try:
        root = ElementTree.parse(selected).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    names = {
        item.attrib.get("Name")
        for item in root.findall(".//PPointData/PDataArray")
    }
    required = {"E_real", "E_imag", "B_real", "B_imag"}
    return selected if required <= names else None


def field_artifact_files(path: Path) -> list[Path]:
    """Return a parallel VTK manifest and every MPI piece it references."""
    if path.suffix.lower() != ".pvtu":
        return [path]
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise PalaceOutputError(f"could not parse Palace field manifest {path}: {exc}") from exc
    pieces = [path.parent / piece.attrib["Source"] for piece in root.iter("Piece")]
    missing = [piece for piece in pieces if not piece.is_file()]
    if missing:
        raise PalaceOutputError(f"{path}: missing field pieces {missing!r}")
    return [path, *pieces]


def parse_mode_fields(
    domain_csv: Path,
    *,
    region_names: dict[int, str],
    output_dir: Path,
) -> list[ModeFieldData]:
    """Parse electric/magnetic participation and energy balance for every mode."""
    if not domain_csv.is_file():
        raise PalaceOutputError(f"missing Palace domain energy output: {domain_csv}")
    with domain_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, skipinitialspace=True))
    if not rows:
        raise PalaceOutputError(f"{domain_csv}: no domain energy rows")

    parsed: list[ModeFieldData] = []
    for row in rows:
        normalized = {str(key).strip(): value for key, value in row.items()}
        mode = int(_finite(normalized.get("m", ""), domain_csv, "mode index"))
        electric: dict[str, float] = {}
        magnetic: dict[str, float] = {}
        for name, raw in normalized.items():
            e_match = re.fullmatch(r"p_elec\[(\d+)\]", name, re.IGNORECASE)
            h_match = re.fullmatch(r"p_mag\[(\d+)\]", name, re.IGNORECASE)
            if e_match:
                index = int(e_match.group(1))
                electric[region_names.get(index, str(index))] = _finite(raw, domain_csv, name)
            elif h_match:
                index = int(h_match.group(1))
                magnetic[region_names.get(index, str(index))] = _finite(raw, domain_csv, name)
        if not electric or not magnetic:
            raise PalaceOutputError(
                f"{domain_csv}: mode {mode} lacks p_elec and p_mag regional columns"
            )
        electric_total = _finite(normalized.get("E_elec (J)", ""), domain_csv, "E_elec")
        magnetic_total = _finite(normalized.get("E_mag (J)", ""), domain_csv, "E_mag")
        denominator = max((abs(electric_total) + abs(magnetic_total)) / 2.0, 1e-300)
        balance = abs(electric_total - magnetic_total) / denominator * 100.0
        localization = sum(
            value for name, value in electric.items() if "resonator" in name.lower()
        )
        parsed.append(
            ModeFieldData(
                mode_index=mode,
                electric_participation=electric,
                magnetic_participation=magnetic,
                resonator_localization=max(0.0, min(1.0, localization)),
                energy_normalization_error_percent=balance,
                field_file=_field_file(output_dir, mode),
            )
        )
    return parsed


def parse_global_error_indicator(path: Path) -> float:
    """Return Palace's final global ``Norm`` indicator as percent."""
    if not path.is_file():
        raise PalaceOutputError(f"missing Palace error indicator output: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, skipinitialspace=True))
    if not rows:
        raise PalaceOutputError(f"{path}: no error indicator rows")
    row = {str(key).strip(): value for key, value in rows[-1].items()}
    key = next((name for name in row if name.lower() == "norm"), None)
    if key is None:
        key = next((name for name in row if "indicator" in name.lower()), None)
    if key is None:
        raise PalaceOutputError(f"{path}: no Norm or global indicator column")
    return _finite(row[key], path, key) * 100.0


def _dof_from_json(value: Any) -> list[int]:
    found: list[int] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("_", " ")
            if ("dof" in normalized or "degree" in normalized) and isinstance(item, int):
                found.append(item)
            found.extend(_dof_from_json(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_dof_from_json(item))
    return found


def parse_degrees_of_freedom(output_dir: Path, stdout_path: Path) -> int:
    """Read DOF from Palace metadata first, then its retained stdout."""
    for path in sorted(output_dir.glob("*.json")):
        try:
            values = _dof_from_json(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        positive = [value for value in values if value > 0]
        if positive:
            return max(positive)
    text = stdout_path.read_text(encoding="utf-8", errors="replace")
    for pattern in _DOF_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            return max(int(value.replace(",", "")) for value in matches)
    raise PalaceOutputError(
        f"could not find Palace degrees of freedom in {output_dir} or {stdout_path}"
    )


_VTK_DTYPES: dict[str, np.dtype[Any]] = {
    "Float32": np.dtype("<f4"),
    "Float64": np.dtype("<f8"),
    "Int32": np.dtype("<i4"),
    "UInt32": np.dtype("<u4"),
    "UInt8": np.dtype("u1"),
}


def _decode_vtk_array(element: ElementTree.Element, source: Path) -> npt.NDArray[Any]:
    encoded = "".join((element.text or "").split())
    if not encoded:
        raise PalaceOutputError(f"{source}: empty VTK DataArray")
    padding = encoded.find("==")
    if padding < 0:
        raise PalaceOutputError(f"{source}: unsupported VTK binary header")
    split = padding + 2
    try:
        header = base64.b64decode(encoded[:split], validate=True)
        words = struct.unpack(f"<{len(header) // 4}I", header)
        block_count, block_size, last_size, *compressed_sizes = words
        compressed = base64.b64decode(encoded[split:], validate=True)
    except (ValueError, struct.error) as exc:
        raise PalaceOutputError(f"{source}: invalid VTK binary array") from exc
    if len(compressed_sizes) != block_count:
        raise PalaceOutputError(f"{source}: invalid VTK compressed-block header")
    raw_parts: list[bytes] = []
    offset = 0
    for size in compressed_sizes:
        try:
            raw_parts.append(zlib.decompress(compressed[offset : offset + size]))
        except zlib.error as exc:
            raise PalaceOutputError(f"{source}: corrupt VTK compressed block") from exc
        offset += size
    raw = b"".join(raw_parts)
    expected = block_size * max(block_count - 1, 0) + (last_size or block_size)
    if len(raw) != expected or offset != len(compressed):
        raise PalaceOutputError(f"{source}: VTK binary array length mismatch")
    dtype = _VTK_DTYPES.get(element.attrib.get("type", ""))
    if dtype is None:
        raise PalaceOutputError(f"{source}: unsupported VTK scalar type")
    values = np.frombuffer(raw, dtype=dtype)
    components = int(element.attrib.get("NumberOfComponents", "1"))
    return values.reshape((-1, components)) if components > 1 else values


def _vtu_vector_data(
    path: Path, kind: str
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.complex128]]:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise PalaceOutputError(f"could not parse Palace field file {path}: {exc}") from exc
    points_element = root.find(".//Points/DataArray")
    point_data = root.find(".//PointData")
    if points_element is None or point_data is None:
        raise PalaceOutputError(f"{path}: missing VTK points or point data")
    prefix = "E" if kind == "electric" else "B"
    named = {item.attrib.get("Name"): item for item in point_data.findall("DataArray")}
    real_element = named.get(f"{prefix}_real")
    imaginary_element = named.get(f"{prefix}_imag")
    if real_element is None or imaginary_element is None:
        raise PalaceOutputError(f"{path}: no complex {kind} vector point data")
    points = np.asarray(_decode_vtk_array(points_element, path), dtype=np.float64)
    real = np.asarray(_decode_vtk_array(real_element, path), dtype=np.float64)
    imaginary = np.asarray(_decode_vtk_array(imaginary_element, path), dtype=np.float64)
    if points.shape != real.shape or real.shape != imaginary.shape or points.shape[1] != 3:
        raise PalaceOutputError(f"{path}: inconsistent Palace field vector dimensions")
    return points, real.astype(np.complex128) + 1j * imaginary


def _vector_data(
    path: Path, kind: str
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.complex128]]:
    point_parts: list[npt.NDArray[np.float64]] = []
    value_parts: list[npt.NDArray[np.complex128]] = []
    for piece in field_artifact_files(path):
        if piece.suffix.lower() == ".pvtu":
            continue
        points, values = _vtu_vector_data(piece, kind)
        point_parts.append(points)
        value_parts.append(values)
    if not point_parts:
        raise PalaceOutputError(f"{path}: no Palace field pieces")
    points = np.concatenate(point_parts)
    values = np.concatenate(value_parts)
    _, unique = np.unique(np.round(points, 10), axis=0, return_index=True)
    return points[unique], values[unique]


def field_overlap(left: Path, right: Path, *, kind: str) -> float:
    """Normalized complex-field overlap after nearest-node mesh projection."""
    if kind not in {"electric", "magnetic"}:
        raise ValueError("kind must be 'electric' or 'magnetic'")
    left_points, left_values = _vector_data(left, kind)
    right_points, right_values = _vector_data(right, kind)
    try:
        from scipy.spatial import cKDTree  # type: ignore[import-untyped]
    except ImportError as exc:
        raise PalaceOutputError("scipy is required to project Palace field meshes") from exc
    if len(left_points) < 4 or len(right_points) < 4:
        raise PalaceOutputError(f"{left} and {right}: fewer than four field samples")
    reference_points, reference_values = (left_points, left_values)
    projected_points, projected_values = (right_points, right_values)
    if len(reference_points) > len(projected_points):
        reference_points, projected_points = projected_points, reference_points
        reference_values, projected_values = projected_values, reference_values
    _, indices = cKDTree(projected_points).query(reference_points, workers=-1)
    left_flat = reference_values.reshape(-1)
    right_flat = projected_values[indices].reshape(-1)
    denominator = float(np.linalg.norm(left_flat) * np.linalg.norm(right_flat))
    if denominator == 0.0:
        raise PalaceOutputError(f"{left} and {right}: zero-norm {kind} field")
    numerator = float(abs(np.vdot(left_flat, right_flat)))
    return max(0.0, min(1.0, numerator / denominator))
