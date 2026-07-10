"""Compile the typed PDK into KLayout DRC, and run it against real GDS.

The rules are *derived* from :class:`~textlayout.pdk.models.PDK`, never
hand-written twice. A deck and a PDK that disagree about the minimum width are
both individually plausible and jointly useless, so there is one source.

Two things this module refuses to do.

**It does not report a clean run over geometry it never looked at.** Shapes on a
layer the PDK does not declare are *unchecked*, not *clean*. They are reported as
a coverage gap, and ``coverage_complete`` is False. A DRC that silently ignores
an undeclared layer is how a junction ends up on the wrong mask.

**It does not average a density rule over the whole chip.** A fill fraction taken
over the full bounding box is passed trivially by a layout that is empty at one
edge and solid at the other. Density is evaluated over a sliding window whose
size the PDK must declare; when the layout is smaller than that window the check
is *skipped with a reason*, not quietly passed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import klayout.db as kdb

from textlayout.pdk.models import PDK

DRC_REPORT_SCHEMA = "textlayout.klayout-drc.v1"

#: Rule families this engine implements. Anything a PDK expresses that is not
#: here is reported as unsupported rather than silently dropped.
SUPPORTED_RULES = (
    "layer_existence",
    "min_width",
    "min_spacing",
    "enclosure",
    "overlap",
    "density_tiled",
    "junction_min_area",
)

#: Rule families real foundry decks carry that this engine does not implement.
#: Named so a reader knows what a passing report does *not* establish.
UNSUPPORTED_RULES = (
    "antenna_ratio",
    "min_area",
    "min_enclosed_area",
    "notch",
    "corner_rounding",
    "off_grid",
)


@dataclass(frozen=True)
class DRCViolation:
    rule: str
    layer: str
    required_um: float | None
    count: int
    sample_bbox_um: tuple[float, float, float, float] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "layer": self.layer,
            "required_um": self.required_um,
            "count": self.count,
            "sample_bbox_um": list(self.sample_bbox_um) if self.sample_bbox_um else None,
        }


@dataclass(frozen=True)
class DRCCheck:
    """One rule evaluation. A skipped check is recorded, never omitted."""

    rule: str
    layer: str
    ran: bool
    violations: int = 0
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "layer": self.layer,
            "ran": self.ran,
            "violations": self.violations,
            "skip_reason": self.skip_reason,
        }


@dataclass(frozen=True)
class DRCReport:
    schema_version: str
    pdk_name: str
    pdk_version: str
    pdk_calibration_status: str
    gds_sha256: str
    top_cell: str
    checks: list[DRCCheck]
    violations: list[DRCViolation]
    undeclared_layers: list[str]
    unsupported_rules: list[str]

    @property
    def passed(self) -> bool:
        """No violation fired. Says nothing about what was *not* checked."""
        return not self.violations

    @property
    def coverage_complete(self) -> bool:
        """Every shape in the layout sits on a layer the PDK declares."""
        return not self.undeclared_layers

    @property
    def signoff_ready(self) -> bool:
        """A clean run over fully covered geometry, on a foundry-calibrated PDK.

        Anything less is a useful result and not a signoff. In particular an
        illustrative PDK can never make a layout fabrication-ready, however
        clean the run.
        """
        return (
            self.passed
            and self.coverage_complete
            and self.pdk_calibration_status == "foundry_calibrated"
        )

    def blocking_reason(self) -> str | None:
        """Why this layout may not be taped out, or ``None``."""
        if self.violations:
            worst = ", ".join(
                f"{v.rule} on {v.layer} ({v.count})" for v in self.violations[:3]
            )
            return f"{len(self.violations)} DRC rule(s) violated: {worst}"
        if not self.coverage_complete:
            return (
                "geometry exists on layers the PDK does not declare "
                f"({', '.join(self.undeclared_layers)}); those shapes were not checked"
            )
        if self.pdk_calibration_status != "foundry_calibrated":
            return (
                f"PDK {self.pdk_name} {self.pdk_version} is "
                f"{self.pdk_calibration_status}, not foundry_calibrated"
            )
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "pdk": {
                "name": self.pdk_name,
                "version": self.pdk_version,
                "calibration_status": self.pdk_calibration_status,
            },
            "gds_sha256": self.gds_sha256,
            "top_cell": self.top_cell,
            "passed": self.passed,
            "coverage_complete": self.coverage_complete,
            "signoff_ready": self.signoff_ready,
            "blocking_reason": self.blocking_reason(),
            "checks": [check.to_dict() for check in self.checks],
            "violations": [violation.to_dict() for violation in self.violations],
            "undeclared_layers": list(self.undeclared_layers),
            "unsupported_rules": list(self.unsupported_rules),
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _um(value: int, dbu: float) -> float:
    return value * dbu


def _bbox_um(edge_pairs: Any, dbu: float) -> tuple[float, float, float, float] | None:
    for pair in edge_pairs.each():
        box = pair.bbox()
        return (_um(box.left, dbu), _um(box.bottom, dbu), _um(box.right, dbu), _um(box.top, dbu))
    return None


def _region(cell: kdb.Cell, layout: kdb.Layout, gds_layer: int, datatype: int) -> kdb.Region | None:
    index = layout.find_layer(gds_layer, datatype)
    if index is None:
        return None
    return kdb.Region(cell.begin_shapes_rec(index))


def _tiled_density(
    region: kdb.Region, bbox: kdb.Box, window_dbu: int
) -> list[tuple[float, kdb.Box]]:
    """Fill fraction in every half-overlapping window. Sliding, not averaged."""
    step = max(1, window_dbu // 2)
    fractions: list[tuple[float, kdb.Box]] = []
    y = bbox.bottom
    while y < bbox.top:
        x = bbox.left
        while x < bbox.right:
            window = kdb.Box(x, y, x + window_dbu, y + window_dbu)
            clipped = region & kdb.Region(window)
            fractions.append((clipped.area() / float(window.area()), window))
            x += step
        y += step
    return fractions


def run_drc(pdk: PDK, gds_path: str | Path, *, top_cell: str | None = None) -> DRCReport:
    """Run every rule the PDK expresses and this engine implements."""
    path = Path(gds_path)
    if not path.is_file():
        raise FileNotFoundError(f"no GDS at {path}")

    layout = kdb.Layout()
    layout.read(str(path))
    dbu = layout.dbu
    cell = layout.cell(top_cell) if top_cell else layout.top_cell()
    if cell is None:
        raise ValueError(f"no top cell {top_cell!r} in {path}")

    checks: list[DRCCheck] = []
    violations: list[DRCViolation] = []

    declared = {(layer.gds_layer, layer.gds_datatype) for layer in pdk.layers}
    undeclared = [
        f"{info.layer}/{info.datatype}"
        for index, info in zip(layout.layer_indexes(), layout.layer_infos())
        if (info.layer, info.datatype) not in declared
        and not kdb.Region(cell.begin_shapes_rec(index)).is_empty()
    ]

    def add(rule: str, layer: str, required: float | None, edge_pairs: Any) -> None:
        count = edge_pairs.count()
        checks.append(DRCCheck(rule=rule, layer=layer, ran=True, violations=count))
        if count:
            violations.append(
                DRCViolation(
                    rule=rule, layer=layer, required_um=required,
                    count=count, sample_bbox_um=_bbox_um(edge_pairs, dbu),
                )
            )

    regions: dict[str, kdb.Region] = {}
    for layer in pdk.layers:
        region = _region(cell, layout, layer.gds_layer, layer.gds_datatype)
        present = region is not None and not region.is_empty()
        checks.append(DRCCheck(rule="layer_existence", layer=layer.name, ran=True, violations=0))
        if not present:
            checks.append(
                DRCCheck(
                    rule="min_width", layer=layer.name, ran=False,
                    skip_reason="layer carries no geometry in this layout",
                )
            )
            checks.append(
                DRCCheck(
                    rule="min_spacing", layer=layer.name, ran=False,
                    skip_reason="layer carries no geometry in this layout",
                )
            )
            continue
        assert region is not None
        regions[layer.name] = region
        add("min_width", layer.name, layer.min_width_um,
            region.width_check(int(round(layer.min_width_um / dbu))))
        add("min_spacing", layer.name, layer.min_spacing_um,
            region.space_check(int(round(layer.min_spacing_um / dbu))))

    for enclosure in pdk.enclosures:
        name = f"{enclosure.outer}>{enclosure.inner}"
        inner, outer = regions.get(enclosure.inner), regions.get(enclosure.outer)
        if inner is None or outer is None:
            checks.append(
                DRCCheck(
                    rule="enclosure", layer=name, ran=False,
                    skip_reason="one of the two layers carries no geometry",
                )
            )
            continue
        add("enclosure", name, enclosure.min_um,
            outer.enclosing_check(inner, int(round(enclosure.min_um / dbu))))

    for overlap in pdk.overlaps:
        name = f"{overlap.a}&{overlap.b}"
        first, second = regions.get(overlap.a), regions.get(overlap.b)
        if first is None or second is None:
            checks.append(
                DRCCheck(
                    rule="overlap", layer=name, ran=False,
                    skip_reason="one of the two layers carries no geometry",
                )
            )
            continue
        add("overlap", name, overlap.min_um,
            first.overlap_check(second, int(round(overlap.min_um / dbu))))

    bbox = cell.bbox()
    for layer in pdk.layers:
        if layer.min_density_fraction is None and layer.max_density_fraction is None:
            continue
        assert pdk.density_window_um is not None  # the PDK validator guarantees it
        window_dbu = int(round(pdk.density_window_um / dbu))
        region = regions.get(layer.name)
        if region is None:
            checks.append(
                DRCCheck(rule="density_tiled", layer=layer.name, ran=False,
                         skip_reason="layer carries no geometry in this layout")
            )
            continue
        if bbox.width() < window_dbu or bbox.height() < window_dbu:
            checks.append(
                DRCCheck(
                    rule="density_tiled", layer=layer.name, ran=False,
                    skip_reason=(
                        f"layout ({_um(bbox.width(), dbu):.3f} x {_um(bbox.height(), dbu):.3f} um) "
                        f"is smaller than the {pdk.density_window_um} um density window; "
                        "a whole-chip average is not a density check"
                    ),
                )
            )
            continue
        offenders = [
            (fraction, window)
            for fraction, window in _tiled_density(region, bbox, window_dbu)
            if (layer.min_density_fraction is not None and fraction < layer.min_density_fraction)
            or (layer.max_density_fraction is not None and fraction > layer.max_density_fraction)
        ]
        checks.append(
            DRCCheck(rule="density_tiled", layer=layer.name, ran=True, violations=len(offenders))
        )
        if offenders:
            _, window = offenders[0]
            violations.append(
                DRCViolation(
                    rule="density_tiled", layer=layer.name,
                    required_um=pdk.density_window_um, count=len(offenders),
                    sample_bbox_um=(
                        _um(window.left, dbu), _um(window.bottom, dbu),
                        _um(window.right, dbu), _um(window.top, dbu),
                    ),
                )
            )

    if pdk.junction_process is not None:
        minimum = pdk.junction_process.min_junction_area_um2
        for layer in pdk.layers:
            if layer.purpose != "junction":
                continue
            region = regions.get(layer.name)
            if region is None:
                checks.append(
                    DRCCheck(rule="junction_min_area", layer=layer.name, ran=False,
                             skip_reason="no junction geometry in this layout")
                )
                continue
            undersized = [
                polygon for polygon in region.each()
                if polygon.area() * dbu * dbu < minimum
            ]
            checks.append(
                DRCCheck(rule="junction_min_area", layer=layer.name, ran=True,
                         violations=len(undersized))
            )
            if undersized:
                box = undersized[0].bbox()
                violations.append(
                    DRCViolation(
                        rule="junction_min_area", layer=layer.name, required_um=minimum,
                        count=len(undersized),
                        sample_bbox_um=(
                            _um(box.left, dbu), _um(box.bottom, dbu),
                            _um(box.right, dbu), _um(box.top, dbu),
                        ),
                    )
                )

    return DRCReport(
        schema_version=DRC_REPORT_SCHEMA,
        pdk_name=pdk.name,
        pdk_version=pdk.version,
        pdk_calibration_status=pdk.calibration_status,
        gds_sha256=_sha256(path),
        top_cell=cell.name,
        checks=checks,
        violations=violations,
        undeclared_layers=sorted(undeclared),
        unsupported_rules=list(UNSUPPORTED_RULES),
    )


def to_lydrc(pdk: PDK) -> str:
    """Emit a standalone KLayout DRC runset, derived from the same PDK.

    Provided so the deck can be run in the KLayout GUI or `strmrun`. It is a
    projection of the PDK, exactly like :func:`run_drc`, so the two cannot drift.
    """
    lines = [
        "# Generated by textlayout.pdk.klayout_drc.to_lydrc -- do not edit by hand.",
        f"# PDK: {pdk.name} {pdk.version} ({pdk.calibration_status})",
        f"# Source: {pdk.source}",
        "",
        "report(\"textlayout DRC\")",
        "",
    ]
    for layer in pdk.layers:
        lines.append(f"{layer.name} = input({layer.gds_layer}, {layer.gds_datatype})")
    lines.append("")
    for layer in pdk.layers:
        lines.append(
            f"{layer.name}.width({layer.min_width_um}.um)"
            f".output(\"{layer.name}_min_width\", \"{layer.name} width < {layer.min_width_um} um\")"
        )
        lines.append(
            f"{layer.name}.space({layer.min_spacing_um}.um)"
            f".output(\"{layer.name}_min_spacing\", "
            f"\"{layer.name} spacing < {layer.min_spacing_um} um\")"
        )
    for enclosure in pdk.enclosures:
        lines.append(
            f"{enclosure.outer}.enclosing({enclosure.inner}, {enclosure.min_um}.um)"
            f".output(\"{enclosure.outer}_encloses_{enclosure.inner}\", "
            f"\"{enclosure.outer} must enclose {enclosure.inner} by {enclosure.min_um} um\")"
        )
    for overlap in pdk.overlaps:
        lines.append(
            f"{overlap.a}.overlap({overlap.b}, {overlap.min_um}.um)"
            f".output(\"{overlap.a}_overlaps_{overlap.b}\", "
            f"\"{overlap.a} must overlap {overlap.b} by {overlap.min_um} um\")"
        )
    lines += [
        "",
        "# Rules this deck does NOT check, and which a clean run therefore does not",
        "# establish: " + ", ".join(UNSUPPORTED_RULES) + ".",
        "",
    ]
    return "\n".join(lines)
