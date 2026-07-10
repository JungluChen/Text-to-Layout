"""KLayout Region boolean helpers."""

from __future__ import annotations

import klayout.db as kdb


def merge(region: kdb.Region) -> kdb.Region:
    return region.merged()


def overlap(a: kdb.Region, b: kdb.Region) -> kdb.Region:
    return a & b


def inside(a: kdb.Region, b: kdb.Region) -> bool:
    return (a - b).is_empty()


def interacting(a: kdb.Region, b: kdb.Region) -> bool:
    return not (a & b).is_empty()

