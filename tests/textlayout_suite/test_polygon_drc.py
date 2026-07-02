"""Polygon-accurate spacing checks that bounding boxes cannot provide."""

from __future__ import annotations

import math

import pytest

from textlayout.models import Polygon
from textlayout.verification.checks import _polygon_gap


def test_diagonal_polygons_with_touching_bboxes_have_nonzero_clearance() -> None:
    lower_left = Polygon("M1", ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)))
    upper_right = Polygon("M1", ((2.0, 2.0), (3.0, 2.0), (2.0, 3.0)))

    assert _polygon_gap(lower_left, upper_right) == pytest.approx(math.sqrt(2.0))


def test_touching_and_nested_polygons_have_zero_clearance() -> None:
    outer = Polygon("M1", ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)))
    touching = Polygon("M1", ((4.0, 1.0), (5.0, 1.0), (5.0, 2.0), (4.0, 2.0)))
    nested = Polygon("M1", ((1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)))

    assert _polygon_gap(outer, touching) == 0.0
    assert _polygon_gap(outer, nested) == 0.0
