from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from textlayout.solvers.palace.parser import field_mac


def _encoded(values: np.ndarray) -> str:
    raw = np.asarray(values, dtype="<f8").tobytes()
    compressed = zlib.compress(raw)
    header = struct.pack("<4I", 1, len(raw), len(raw), len(compressed))
    return base64.b64encode(header).decode() + base64.b64encode(compressed).decode()


def _write_field(path: Path, electric: np.ndarray, magnetic: np.ndarray) -> None:
    points = np.asarray(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float
    )
    zero = np.zeros_like(electric)
    arrays = {
        "E_real": electric,
        "E_imag": zero,
        "B_real": magnetic,
        "B_imag": zero,
    }
    point_data = "\n".join(
        f'<DataArray type="Float64" Name="{name}" NumberOfComponents="3" format="binary">{_encoded(value)}</DataArray>'
        for name, value in arrays.items()
    )
    path.write_text(
        "<VTKFile><UnstructuredGrid><Piece>"
        f"<PointData>{point_data}</PointData>"
        f'<Points><DataArray type="Float64" NumberOfComponents="3" format="binary">{_encoded(points)}</DataArray></Points>'
        "</Piece></UnstructuredGrid></VTKFile>",
        encoding="utf-8",
    )


def test_field_mac_is_one_for_identical_complex_vector_fields(tmp_path: Path) -> None:
    electric = np.asarray([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0]], dtype=float)
    magnetic = np.asarray([[0, 1, 0], [1, 0, 0], [0, 1, 1], [1, 0, 1]], dtype=float)
    left = tmp_path / "left.vtu"
    right = tmp_path / "right.vtu"
    _write_field(left, electric, magnetic)
    _write_field(right, electric, magnetic)
    assert field_mac(left, right, kind="electric") == pytest.approx(1.0)
    assert field_mac(left, right, kind="magnetic") == pytest.approx(1.0)


def test_field_mac_rejects_orthogonal_electric_fields(tmp_path: Path) -> None:
    left = tmp_path / "left.vtu"
    right = tmp_path / "right.vtu"
    ex = np.tile([1.0, 0.0, 0.0], (4, 1))
    ey = np.tile([0.0, 1.0, 0.0], (4, 1))
    magnetic = np.tile([0.0, 0.0, 1.0], (4, 1))
    _write_field(left, ex, magnetic)
    _write_field(right, ey, magnetic)
    assert field_mac(left, right, kind="electric") == pytest.approx(0.0)

