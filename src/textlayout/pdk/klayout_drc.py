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
import json
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
    "min_area",
    "notch",
    "separation",
    "enclosure",
    "overlap",
    "density_tiled",
    "junction_min_area",
)

# Rule families the emitted standalone Ruby DRC deck is allowed to claim. The
# Python backend may support more families; parity tests compare the overlap.
STANDALONE_SUPPORTED_RULES = (
    "layer_existence",
    "min_width",
    "min_spacing",
    "min_area",
    "notch",
    "separation",
    "enclosure",
    "overlap",
    "junction_min_area",
)

#: Rule families real foundry decks carry that this engine does not implement.
#: Named so a reader knows what a passing report does *not* establish.
UNSUPPORTED_RULES = (
    "acute_angle",
    "antenna_ratio",
    "floating_conductor",
    "min_enclosed_area",
    "corner_rounding",
    "off_grid",
    "port_marker_placement",
    "junction_max_area",
    "junction_lead_overlap",
)


@dataclass(frozen=True)
class CompiledDRCRule:
    rule_id: str
    family: str
    layers: tuple[str, ...]
    threshold: float | None
    unit: str
    severity: str
    mandatory: bool
    supported_backends: set[str]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "family": self.family,
            "layers": list(self.layers),
            "threshold": self.threshold,
            "unit": self.unit,
            "severity": self.severity,
            "mandatory": self.mandatory,
            "supported_backends": sorted(self.supported_backends),
            "description": self.description,
        }


@dataclass(frozen=True)
class DRCViolation:
    rule: str
    layer: str
    required_um: float | None
    count: int
    sample_bbox_um: tuple[float, float, float, float] | None
    rule_id: str = ""
    description: str = ""
    severity: str = "error"
    value: float = 0.0
    unit: str = "um"
    pdk_source: str = ""
    pdk_hash: str = ""
    runset_hash: str = ""
    mandatory: bool = True
    blocking: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule": self.rule,
            "description": self.description,
            "severity": self.severity,
            "layer": self.layer,
            "required_um": self.required_um,
            "value": self.value,
            "unit": self.unit,
            "pdk_source": self.pdk_source,
            "source_pdk_path": self.pdk_source,
            "pdk_hash": self.pdk_hash,
            "runset_hash": self.runset_hash,
            "mandatory": self.mandatory,
            "blocking": self.blocking,
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
    rule_id: str = ""
    description: str = ""
    severity: str = "error"
    value: float = 0.0
    unit: str = "um"
    pdk_source: str = ""
    pdk_hash: str = ""
    runset_hash: str = ""
    mandatory: bool = True
    supported_backends: tuple[str, ...] = ("python",)
    skip_kind: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule": self.rule,
            "description": self.description,
            "severity": self.severity,
            "layer": self.layer,
            "ran": self.ran,
            "violations": self.violations,
            "skip_reason": self.skip_reason,
            "value": self.value,
            "unit": self.unit,
            "pdk_source": self.pdk_source,
            "source_pdk_path": self.pdk_source,
            "pdk_hash": self.pdk_hash,
            "runset_hash": self.runset_hash,
            "mandatory": self.mandatory,
            "supported_backends": list(self.supported_backends),
            "skip_kind": self.skip_kind,
            "details": self.details or {},
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
    unsupported_mandatory_rules: list[str]
    compiled_rules: list[CompiledDRCRule]
    deck_fixture_validated: bool = False

    @property
    def passed(self) -> bool:
        """No violation fired. Says nothing about what was *not* checked."""
        return not self.violations

    @property
    def geometrically_clean(self) -> bool:
        return not any(v.severity == "error" for v in self.violations)

    @property
    def coverage_complete(self) -> bool:
        """Every shape and every required layer is covered by the declared PDK."""
        return not self.undeclared_layers and not any(
            violation.rule_id == "PDK.REQUIRED_LAYER_MISSING"
            for violation in self.violations
        )

    @property
    def skipped_mandatory_checks(self) -> list[DRCCheck]:
        return [
            check for check in self.checks
            if check.mandatory and not check.ran and check.skip_kind == "skipped_mandatory_rule"
        ]

    @property
    def mandatory_checks_complete(self) -> bool:
        return not self.skipped_mandatory_checks

    @property
    def pdk_calibrated(self) -> bool:
        return self.pdk_calibration_status == "foundry_calibrated"

    @property
    def signoff_ready(self) -> bool:
        """True only when all signoff prerequisites have been demonstrated."""
        return (
            self.geometrically_clean
            and self.coverage_complete
            and self.mandatory_checks_complete
            and not self.unsupported_mandatory_rules
            and self.pdk_calibrated
            and self.deck_fixture_validated
        )

    def blocking_reason(self) -> str | None:
        """Why this layout may not be taped out, or ``None``."""
        if self.violations:
            worst = ", ".join(
                f"{v.rule} on {v.layer} ({v.count})" for v in self.violations[:3]
            )
            return f"{len(self.violations)} DRC rule(s) violated: {worst}"
        if self.undeclared_layers:
            return (
                "geometry exists on layers the PDK does not declare "
                f"({', '.join(self.undeclared_layers)}); those shapes were not checked"
            )
        if not self.coverage_complete:
            return "one or more required PDK layers are missing"
        if not self.mandatory_checks_complete:
            skipped = ", ".join(check.rule_id for check in self.skipped_mandatory_checks[:3])
            return f"mandatory DRC checks were skipped: {skipped}"
        if self.unsupported_mandatory_rules:
            return (
                "mandatory DRC rule families are unsupported: "
                + ", ".join(self.unsupported_mandatory_rules)
            )
        if not self.pdk_calibrated:
            return (
                f"PDK {self.pdk_name} {self.pdk_version} is "
                f"{self.pdk_calibration_status}, not foundry_calibrated"
            )
        if not self.deck_fixture_validated:
            return "generated standalone DRC deck fixture validation has not passed"
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
            "geometrically_clean": self.geometrically_clean,
            "coverage_complete": self.coverage_complete,
            "mandatory_checks_complete": self.mandatory_checks_complete,
            "unsupported_mandatory_rules": list(self.unsupported_mandatory_rules),
            "pdk_calibrated": self.pdk_calibrated,
            "deck_fixture_validated": self.deck_fixture_validated,
            "signoff_ready": self.signoff_ready,
            "blocking_reason": self.blocking_reason(),
            "compiled_rules": [rule.to_dict() for rule in self.compiled_rules],
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


def _pdk_hash(pdk: PDK) -> str:
    payload = json.dumps(pdk.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rule_metadata(
    *,
    rule: str,
    layer: str,
    description: str,
    value: float = 0.0,
    unit: str = "um",
    pdk: PDK,
    pdk_hash: str,
    runset_hash: str,
    severity: str = "error",
    rule_id: str | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id
        or _canonical_rule_id(pdk.name, rule, layer),
        "description": description,
        "severity": severity,
        "value": value,
        "unit": unit,
        "pdk_source": pdk.source,
        "pdk_hash": pdk_hash,
        "runset_hash": runset_hash,
    }


def _canonical_rule_id(pdk_name: str, rule: str, layer: str) -> str:
    canonical = {
        ("min_width", "IDC_FINGER"): "IDC.MIN_FINGER_WIDTH",
        ("min_spacing", "IDC_FINGER"): "IDC.MIN_FINGER_SPACING",
        ("min_width", "IDC_BUS"): "IDC.MIN_BUS_WIDTH",
        ("separation", "IDC_P&IDC_N"): "IDC.NO_UNINTENDED_BRIDGE",
        ("min_width", "CPW_SIGNAL"): "CPW.MIN_CENTER_CONDUCTOR_WIDTH",
        ("separation", "CPW_SIGNAL&CPW_GROUND"): "CPW.MIN_SIGNAL_GROUND_GAP",
        ("min_width", "SPIRAL_TRACE"): "SPIRAL.MIN_TRACE_WIDTH",
        ("min_spacing", "SPIRAL_TRACE"): "SPIRAL.MIN_TURN_SPACING",
        ("junction_min_area", "JJ"): "JJ.MIN_AREA",
        ("overlap", "JJ&M1"): "JJ.MIN_LEAD_OVERLAP",
        ("enclosure", "M1>JJ"): "JJ.MIN_LARGE_METAL_ENCLOSURE",
    }
    return canonical.get(
        (rule, layer),
        f"{pdk_name}.{rule}.{layer}".replace(">", "_contains_").replace("&", "_and_"),
    )


def _requirement_map(pdk: PDK) -> dict[str, bool]:
    required = {family: False for family in UNSUPPORTED_RULES}
    for family in SUPPORTED_RULES:
        required[family] = True
    for requirement in pdk.rule_requirements:
        required[requirement.rule_family] = requirement.mandatory
    return required


def _mandatory(pdk: PDK, family: str) -> bool:
    return _requirement_map(pdk).get(family, False)


def _backends_for(family: str) -> set[str]:
    backends = {"python"} if family in SUPPORTED_RULES else set()
    if family in STANDALONE_SUPPORTED_RULES:
        backends.add("standalone")
    return backends


def _rule(
    pdk: PDK,
    family: str,
    layers: tuple[str, ...],
    threshold: float | None,
    unit: str,
    description: str,
    *,
    rule_id: str | None = None,
    mandatory: bool | None = None,
    severity: str = "error",
) -> CompiledDRCRule:
    layer_key = (
        layers[0]
        if len(layers) == 1
        else f"{layers[0]}>{layers[1]}"
        if family == "enclosure"
        else "&".join(layers)
    )
    return CompiledDRCRule(
        rule_id=rule_id or _canonical_rule_id(pdk.name, family, layer_key),
        family=family,
        layers=layers,
        threshold=threshold,
        unit=unit,
        severity=severity,
        mandatory=_mandatory(pdk, family) if mandatory is None else mandatory,
        supported_backends=_backends_for(family),
        description=description,
    )


def compile_drc_rules(pdk: PDK) -> list[CompiledDRCRule]:
    """Compile a PDK into the single rule list used by all DRC backends."""
    rules: list[CompiledDRCRule] = []
    for layer in pdk.layers:
        rules.append(
            _rule(
                pdk,
                "layer_existence",
                (layer.name,),
                None,
                "presence",
                f"Declared PDK layer {layer.name} is considered during DRC.",
                rule_id="PDK.REQUIRED_LAYER_MISSING" if layer.required else None,
                mandatory=layer.required,
            )
        )
        rules.append(
            _rule(
                pdk,
                "min_width",
                (layer.name,),
                layer.min_width_um,
                "um",
                f"{layer.name} width must be at least {layer.min_width_um} um.",
            )
        )
        rules.append(
            _rule(
                pdk,
                "min_spacing",
                (layer.name,),
                layer.min_spacing_um,
                "um",
                f"{layer.name} spacing must be at least {layer.min_spacing_um} um.",
            )
        )
        min_area_um2 = layer.min_width_um * layer.min_width_um
        rules.append(
            _rule(
                pdk,
                "min_area",
                (layer.name,),
                min_area_um2,
                "um^2",
                f"{layer.name} feature area must be at least {min_area_um2:.6g} um^2.",
            )
        )
        rules.append(
            _rule(
                pdk,
                "notch",
                (layer.name,),
                layer.min_spacing_um,
                "um",
                f"{layer.name} internal notch width must be at least {layer.min_spacing_um} um.",
            )
        )
        if layer.min_density_fraction is not None or layer.max_density_fraction is not None:
            rules.append(
                _rule(
                    pdk,
                    "density_tiled",
                    (layer.name,),
                    pdk.density_window_um,
                    "um",
                    "Layer density must stay inside the declared local window bounds.",
                )
            )
        if pdk.junction_process is not None and layer.purpose == "junction":
            minimum = pdk.junction_process.min_junction_area_um2
            rules.append(
                _rule(
                    pdk,
                    "junction_min_area",
                    (layer.name,),
                    minimum,
                    "um^2",
                    f"Junction area on {layer.name} must be at least {minimum} um^2.",
                )
            )
    for separation in pdk.separations:
        rules.append(
            _rule(
                pdk,
                "separation",
                (separation.a, separation.b),
                separation.min_um,
                "um",
                separation.description
                or f"{separation.a} and {separation.b} must be separated by {separation.min_um} um.",
                rule_id=separation.rule_id,
            )
        )
    for enclosure in pdk.enclosures:
        rules.append(
            _rule(
                pdk,
                "enclosure",
                (enclosure.outer, enclosure.inner),
                enclosure.min_um,
                "um",
                f"{enclosure.outer} must enclose {enclosure.inner} by {enclosure.min_um} um.",
            )
        )
    for overlap in pdk.overlaps:
        rules.append(
            _rule(
                pdk,
                "overlap",
                (overlap.a, overlap.b),
                overlap.min_um,
                "um",
                f"{overlap.a} and {overlap.b} must overlap by {overlap.min_um} um.",
            )
        )
    declared_families = {rule.family for rule in rules}
    for family, mandatory in sorted(_requirement_map(pdk).items()):
        if family in declared_families or family in SUPPORTED_RULES:
            continue
        rules.append(
            CompiledDRCRule(
                rule_id=f"{pdk.name}.unsupported.{family}",
                family=family,
                layers=(),
                threshold=None,
                unit="",
                severity="error",
                mandatory=mandatory,
                supported_backends=set(),
                description=f"Rule family {family} is declared but not implemented.",
            )
        )
    return rules


def _um(value: int, dbu: float) -> float:
    return value * dbu


def _bbox_um(edge_pairs: Any, dbu: float) -> tuple[float, float, float, float] | None:
    for pair in edge_pairs.each():
        box = pair.bbox()
        return (_um(box.left, dbu), _um(box.bottom, dbu), _um(box.right, dbu), _um(box.top, dbu))
    return None


def _region_bbox_um(region: kdb.Region, dbu: float) -> tuple[float, float, float, float] | None:
    for polygon in region.each():
        box = polygon.bbox()
        return (_um(box.left, dbu), _um(box.bottom, dbu), _um(box.right, dbu), _um(box.top, dbu))
    return None


def _region(cell: kdb.Cell, layout: kdb.Layout, gds_layer: int, datatype: int) -> kdb.Region | None:
    index = layout.find_layer(gds_layer, datatype)
    if index is None:
        return None
    return kdb.Region(cell.begin_shapes_rec(index))


def _tiled_density(
    region: kdb.Region,
    bbox: kdb.Box,
    *,
    window_dbu: int,
    stride_dbu: int,
    boundary_policy: str,
) -> tuple[list[tuple[float, kdb.Box]], dict[str, Any]]:
    """Fill fraction in policy-defined local windows."""
    fractions: list[tuple[float, kdb.Box]] = []
    skipped_edge_windows = 0
    min_density: float | None = None
    max_density: float | None = None
    y = bbox.bottom
    while y < bbox.top:
        x = bbox.left
        while x < bbox.right:
            nominal = kdb.Box(x, y, x + window_dbu, y + window_dbu)
            if boundary_policy == "FULL_WINDOWS_ONLY":
                if nominal.right > bbox.right or nominal.top > bbox.top:
                    skipped_edge_windows += 1
                    x += stride_dbu
                    continue
                window = nominal
            elif boundary_policy == "CLIP_TO_ANALYSIS_BOUNDARY":
                window = kdb.Box(
                    max(nominal.left, bbox.left),
                    max(nominal.bottom, bbox.bottom),
                    min(nominal.right, bbox.right),
                    min(nominal.top, bbox.top),
                )
                if window.area() <= 0:
                    skipped_edge_windows += 1
                    x += stride_dbu
                    continue
            else:
                raise ValueError(
                    "EXPLICIT_DENSITY_BOUNDARY is not implemented by the local "
                    "KLayout Region backend"
                )
            clipped = region & kdb.Region(window)
            density = clipped.area() / float(window.area())
            min_density = density if min_density is None else min(min_density, density)
            max_density = density if max_density is None else max(max_density, density)
            fractions.append((density, window))
            x += stride_dbu
        y += stride_dbu
    return fractions, {
        "analysis_boundary_dbu": [bbox.left, bbox.bottom, bbox.right, bbox.top],
        "boundary_policy": boundary_policy,
        "window_dbu": window_dbu,
        "stride_dbu": stride_dbu,
        "number_of_windows": len(fractions),
        "minimum_density": min_density,
        "maximum_density": max_density,
        "skipped_edge_windows": skipped_edge_windows,
    }


def run_drc(
    pdk: PDK,
    gds_path: str | Path,
    *,
    top_cell: str | None = None,
    deck_fixture_validated: bool = False,
) -> DRCReport:
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
    compiled_rules = compile_drc_rules(pdk)
    pdk_hash = _pdk_hash(pdk)
    runset_hash = hashlib.sha256(to_lydrc(pdk).encode("utf-8")).hexdigest()
    unsupported_mandatory = sorted(
        {
            rule.family
            for rule in compiled_rules
            if rule.mandatory and (not rule.supported_backends or "standalone" not in rule.supported_backends)
        }
    )

    declared = {(layer.gds_layer, layer.gds_datatype) for layer in pdk.layers}
    undeclared = [
        f"{info.layer}/{info.datatype}"
        for index, info in zip(layout.layer_indexes(), layout.layer_infos())
        if (info.layer, info.datatype) not in declared
        and not kdb.Region(cell.begin_shapes_rec(index)).is_empty()
    ]

    def add(
        rule: str,
        layer: str,
        required: float | None,
        edge_pairs: Any,
        description: str,
        *,
        unit: str = "um",
    ) -> None:
        count = edge_pairs.count()
        metadata = _rule_metadata(
            rule=rule,
            layer=layer,
            description=description,
            value=float(required or 0.0),
            unit=unit,
            pdk=pdk,
            pdk_hash=pdk_hash,
            runset_hash=runset_hash,
        )
        checks.append(DRCCheck(rule=rule, layer=layer, ran=True, violations=count, **metadata))
        if count:
            violations.append(
                DRCViolation(
                    rule=rule, layer=layer, required_um=required,
                    count=count, sample_bbox_um=_bbox_um(edge_pairs, dbu),
                    **metadata,
                )
            )

    regions: dict[str, kdb.Region] = {}
    for layer in pdk.layers:
        region = _region(cell, layout, layer.gds_layer, layer.gds_datatype)
        present = region is not None and not region.is_empty()
        layer_existence_metadata = _rule_metadata(
            rule="layer_existence",
            layer=layer.name,
            description=f"Declared PDK layer {layer.name} is considered during DRC.",
            pdk=pdk,
            pdk_hash=pdk_hash,
            runset_hash=runset_hash,
            rule_id="PDK.REQUIRED_LAYER_MISSING" if layer.required else None,
        )
        checks.append(
            DRCCheck(
                rule="layer_existence",
                layer=layer.name,
                ran=True,
                violations=0 if present or not layer.required else 1,
                mandatory=layer.required,
                supported_backends=tuple(sorted(_backends_for("layer_existence"))),
                **layer_existence_metadata,
            )
        )
        if not present:
            if layer.required:
                violations.append(
                    DRCViolation(
                        rule="layer_existence",
                        layer=layer.name,
                        required_um=None,
                        count=1,
                        sample_bbox_um=None,
                        mandatory=True,
                        blocking=True,
                        **layer_existence_metadata,
                    )
                )
            checks.append(
                DRCCheck(
                    rule="min_width", layer=layer.name, ran=False,
                    skip_reason="layer carries no geometry in this layout",
                    mandatory=layer.required,
                    skip_kind="skipped_mandatory_rule" if layer.required else "skipped_optional_rule",
                    **_rule_metadata(
                        rule="min_width",
                        layer=layer.name,
                        description=f"{layer.name} width must be at least {layer.min_width_um} um.",
                        value=layer.min_width_um,
                        pdk=pdk,
                        pdk_hash=pdk_hash,
                        runset_hash=runset_hash,
                    ),
                )
            )
            checks.append(
                DRCCheck(
                    rule="min_spacing", layer=layer.name, ran=False,
                    skip_reason="layer carries no geometry in this layout",
                    mandatory=layer.required,
                    skip_kind="skipped_mandatory_rule" if layer.required else "skipped_optional_rule",
                    **_rule_metadata(
                        rule="min_spacing",
                        layer=layer.name,
                        description=f"{layer.name} spacing must be at least {layer.min_spacing_um} um.",
                        value=layer.min_spacing_um,
                        pdk=pdk,
                        pdk_hash=pdk_hash,
                        runset_hash=runset_hash,
                    ),
                )
            )
            continue
        assert region is not None
        regions[layer.name] = region
        add("min_width", layer.name, layer.min_width_um,
            region.width_check(int(round(layer.min_width_um / dbu))),
            f"{layer.name} width must be at least {layer.min_width_um} um.")
        add("min_spacing", layer.name, layer.min_spacing_um,
            region.space_check(int(round(layer.min_spacing_um / dbu))),
            f"{layer.name} spacing must be at least {layer.min_spacing_um} um.")
        min_area_um2 = layer.min_width_um * layer.min_width_um
        undersized_polygons = [
            polygon
            for polygon in region.each()
            if polygon.area() * dbu * dbu < min_area_um2
        ]
        undersized_region = kdb.Region()
        for polygon in undersized_polygons:
            undersized_region.insert(polygon)
        min_area_metadata = _rule_metadata(
            rule="min_area",
            layer=layer.name,
            description=(
                f"{layer.name} feature area must be at least "
                f"{min_area_um2:.6g} um^2."
            ),
            value=min_area_um2,
            unit="um^2",
            pdk=pdk,
            pdk_hash=pdk_hash,
            runset_hash=runset_hash,
        )
        checks.append(
            DRCCheck(
                rule="min_area",
                layer=layer.name,
                ran=True,
                violations=len(undersized_polygons),
                **min_area_metadata,
            )
        )
        if undersized_polygons:
            violations.append(
                DRCViolation(
                    rule="min_area",
                    layer=layer.name,
                    required_um=min_area_um2,
                    count=len(undersized_polygons),
                    sample_bbox_um=_region_bbox_um(undersized_region, dbu),
                    **min_area_metadata,
                )
            )
        notch_pairs = region.notch_check(int(round(layer.min_spacing_um / dbu)))
        add(
            "notch",
            layer.name,
            layer.min_spacing_um,
            notch_pairs,
            f"{layer.name} internal notch width must be at least {layer.min_spacing_um} um.",
        )

    for separation in pdk.separations:
        name = f"{separation.a}&{separation.b}"
        first, second = regions.get(separation.a), regions.get(separation.b)
        if first is None or second is None:
            checks.append(
                DRCCheck(
                    rule="separation", layer=name, ran=False,
                    skip_reason="one of the two layers carries no geometry",
                    mandatory=False,
                    skip_kind="skipped_optional_rule",
                    **_rule_metadata(
                        rule="separation",
                        layer=name,
                        description=separation.description
                        or f"{separation.a} and {separation.b} must be separated by {separation.min_um} um.",
                        value=separation.min_um,
                        pdk=pdk,
                        pdk_hash=pdk_hash,
                        runset_hash=runset_hash,
                        rule_id=separation.rule_id,
                    ),
                )
            )
            continue
        distance = int(round(separation.min_um / dbu))
        offenders = first.sized(distance) & second
        metadata = _rule_metadata(
            rule="separation",
            layer=name,
            description=separation.description
            or f"{separation.a} and {separation.b} must be separated by {separation.min_um} um.",
            value=separation.min_um,
            pdk=pdk,
            pdk_hash=pdk_hash,
            runset_hash=runset_hash,
            rule_id=separation.rule_id,
        )
        checks.append(
            DRCCheck(
                rule="separation",
                layer=name,
                ran=True,
                violations=offenders.count(),
                **metadata,
            )
        )
        if offenders.count():
            violations.append(
                DRCViolation(
                    rule="separation",
                    layer=name,
                    required_um=separation.min_um,
                    count=offenders.count(),
                    sample_bbox_um=_region_bbox_um(offenders, dbu),
                    **metadata,
                )
            )

    for enclosure in pdk.enclosures:
        name = f"{enclosure.outer}>{enclosure.inner}"
        inner, outer = regions.get(enclosure.inner), regions.get(enclosure.outer)
        if inner is None or outer is None:
            checks.append(
                DRCCheck(
                    rule="enclosure", layer=name, ran=False,
                    skip_reason="one of the two layers carries no geometry",
                    mandatory=False,
                    skip_kind="skipped_optional_rule",
                    **_rule_metadata(
                        rule="enclosure",
                        layer=name,
                        description=(
                            f"{enclosure.outer} must enclose {enclosure.inner} by "
                            f"{enclosure.min_um} um."
                        ),
                        value=enclosure.min_um,
                        pdk=pdk,
                        pdk_hash=pdk_hash,
                        runset_hash=runset_hash,
                    ),
                )
            )
            continue
        add("enclosure", name, enclosure.min_um,
            outer.enclosing_check(inner, int(round(enclosure.min_um / dbu))),
            f"{enclosure.outer} must enclose {enclosure.inner} by {enclosure.min_um} um.")

    for overlap in pdk.overlaps:
        name = f"{overlap.a}&{overlap.b}"
        first, second = regions.get(overlap.a), regions.get(overlap.b)
        if first is None or second is None:
            checks.append(
                DRCCheck(
                    rule="overlap", layer=name, ran=False,
                    skip_reason="one of the two layers carries no geometry",
                    mandatory=False,
                    skip_kind="skipped_optional_rule",
                    **_rule_metadata(
                        rule="overlap",
                        layer=name,
                        description=f"{overlap.a} and {overlap.b} must overlap by {overlap.min_um} um.",
                        value=overlap.min_um,
                        pdk=pdk,
                        pdk_hash=pdk_hash,
                        runset_hash=runset_hash,
                    ),
                )
            )
            continue
        add("overlap", name, overlap.min_um,
            first.overlap_check(second, int(round(overlap.min_um / dbu))),
            f"{overlap.a} and {overlap.b} must overlap by {overlap.min_um} um.")

    bbox = cell.bbox()
    for layer in pdk.layers:
        if layer.min_density_fraction is None and layer.max_density_fraction is None:
            continue
        assert pdk.density_window_um is not None  # the PDK validator guarantees it
        window_dbu = int(round(pdk.density_window_um / dbu))
        stride_um = pdk.density_stride_um or (pdk.density_window_um / 2.0)
        stride_dbu = max(1, int(round(stride_um / dbu)))
        region = regions.get(layer.name)
        density_base_details = {
            "window_size_um": pdk.density_window_um,
            "stride_um": stride_um,
            "boundary_policy": pdk.density_boundary_policy,
            "analysis_boundary_um": [
                _um(bbox.left, dbu), _um(bbox.bottom, dbu),
                _um(bbox.right, dbu), _um(bbox.top, dbu),
            ],
        }
        if region is None:
            checks.append(
                DRCCheck(rule="density_tiled", layer=layer.name, ran=False,
                         skip_reason="layer carries no geometry in this layout",
                         mandatory=layer.required,
                         skip_kind="skipped_mandatory_rule" if layer.required else "skipped_optional_rule",
                         **_rule_metadata(
                             rule="density_tiled",
                             layer=layer.name,
                             description="Layer density must stay inside the declared local window bounds.",
                             value=pdk.density_window_um or 0.0,
                             pdk=pdk,
                             pdk_hash=pdk_hash,
                             runset_hash=runset_hash,
                         ),
                         details={**density_base_details, "number_of_windows": 0})
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
                    mandatory=True,
                    skip_kind="skipped_mandatory_rule",
                    **_rule_metadata(
                        rule="density_tiled",
                        layer=layer.name,
                        description="Layer density must stay inside the declared local window bounds.",
                        value=pdk.density_window_um or 0.0,
                        pdk=pdk,
                        pdk_hash=pdk_hash,
                        runset_hash=runset_hash,
                    ),
                    details={**density_base_details, "number_of_windows": 0},
                )
            )
            continue
        density_results, density_summary = _tiled_density(
            region,
            bbox,
            window_dbu=window_dbu,
            stride_dbu=stride_dbu,
            boundary_policy=pdk.density_boundary_policy,
        )
        density_summary = {**density_summary, **density_base_details}
        density_offenders = [
            (fraction, window)
            for fraction, window in density_results
            if (layer.min_density_fraction is not None and fraction < layer.min_density_fraction)
            or (layer.max_density_fraction is not None and fraction > layer.max_density_fraction)
        ]
        checks.append(
            DRCCheck(
                rule="density_tiled",
                layer=layer.name,
                ran=True,
                violations=len(density_offenders),
                **_rule_metadata(
                    rule="density_tiled",
                    layer=layer.name,
                    description="Layer density must stay inside the declared local window bounds.",
                    value=pdk.density_window_um or 0.0,
                    pdk=pdk,
                    pdk_hash=pdk_hash,
                    runset_hash=runset_hash,
                ),
                details=density_summary,
            )
        )
        if density_offenders:
            _, window = density_offenders[0]
            density_metadata = _rule_metadata(
                rule="density_tiled",
                layer=layer.name,
                description="Layer density must stay inside the declared local window bounds.",
                value=pdk.density_window_um or 0.0,
                pdk=pdk,
                pdk_hash=pdk_hash,
                runset_hash=runset_hash,
            )
            violations.append(
                DRCViolation(
                    rule="density_tiled", layer=layer.name,
                    required_um=pdk.density_window_um, count=len(density_offenders),
                    sample_bbox_um=(
                        _um(window.left, dbu), _um(window.bottom, dbu),
                        _um(window.right, dbu), _um(window.top, dbu),
                    ),
                    **density_metadata,
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
                             skip_reason="no junction geometry in this layout",
                             mandatory=layer.required,
                             skip_kind="skipped_mandatory_rule" if layer.required else "skipped_optional_rule",
                             **_rule_metadata(
                                 rule="junction_min_area",
                                 layer=layer.name,
                                 description=(
                                     f"Junction area on {layer.name} must be at least "
                                     f"{minimum} um^2."
                                 ),
                                 value=minimum,
                                 unit="um^2",
                                 pdk=pdk,
                                 pdk_hash=pdk_hash,
                                 runset_hash=runset_hash,
                             ))
                )
                continue
            undersized = [
                polygon for polygon in region.each()
                if polygon.area() * dbu * dbu < minimum
            ]
            checks.append(
                DRCCheck(rule="junction_min_area", layer=layer.name, ran=True,
                         violations=len(undersized),
                         **_rule_metadata(
                             rule="junction_min_area",
                             layer=layer.name,
                             description=(
                                 f"Junction area on {layer.name} must be at least "
                                 f"{minimum} um^2."
                             ),
                             value=minimum,
                             unit="um^2",
                             pdk=pdk,
                             pdk_hash=pdk_hash,
                             runset_hash=runset_hash,
                         ))
            )
            if undersized:
                box = undersized[0].bbox()
                junction_metadata = _rule_metadata(
                    rule="junction_min_area",
                    layer=layer.name,
                    description=f"Junction area on {layer.name} must be at least {minimum} um^2.",
                    value=minimum,
                    unit="um^2",
                    pdk=pdk,
                    pdk_hash=pdk_hash,
                    runset_hash=runset_hash,
                )
                violations.append(
                    DRCViolation(
                        rule="junction_min_area", layer=layer.name, required_um=minimum,
                        count=len(undersized),
                        sample_bbox_um=(
                            _um(box.left, dbu), _um(box.bottom, dbu),
                            _um(box.right, dbu), _um(box.top, dbu),
                        ),
                        **junction_metadata,
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
        unsupported_mandatory_rules=unsupported_mandatory,
        compiled_rules=compiled_rules,
        deck_fixture_validated=deck_fixture_validated,
    )


def to_lydrc(pdk: PDK) -> str:
    """Emit a standalone KLayout DRC runset, derived from the same PDK.

    Provided so the deck can be run in the KLayout GUI or `strmrun`. It is a
    projection of the PDK, exactly like :func:`run_drc`, so the two cannot drift.
    """
    rules = compile_drc_rules(pdk)
    by_name = {layer.name: layer for layer in pdk.layers}
    lines = [
        "# Generated by textlayout.pdk.klayout_drc.to_lydrc -- do not edit by hand.",
        f"# PDK: {pdk.name} {pdk.version} ({pdk.calibration_status})",
        f"# Source: {pdk.source}",
        "",
        "report(\"textlayout DRC\", $report)",
        "",
    ]
    for layer in pdk.layers:
        lines.append(f"{layer.name} = input({layer.gds_layer}, {layer.gds_datatype})")
    lines.append("")
    for rule in rules:
        if "standalone" not in rule.supported_backends:
            continue
        if rule.family == "layer_existence":
            continue
        description = rule.description.replace("\\", "\\\\").replace('"', '\\"')
        threshold = rule.threshold or 0.0
        if rule.family == "min_width":
            lines.append(
                f"{rule.layers[0]}.width({threshold}.um)"
                f".output(\"{rule.rule_id}\", \"{description}\")"
            )
        elif rule.family == "min_spacing":
            lines.append(
                f"{rule.layers[0]}.space({threshold}.um)"
                f".output(\"{rule.rule_id}\", \"{description}\")"
            )
        elif rule.family == "min_area":
            lines.append(
                f"{rule.layers[0]}.with_area(nil, {threshold}.um2)"
                f".output(\"{rule.rule_id}\", \"{description}\")"
            )
        elif rule.family == "notch":
            lines.append(
                f"{rule.layers[0]}.notch({threshold}.um)"
                f".output(\"{rule.rule_id}\", \"{description}\")"
            )
        elif rule.family == "separation":
            lines.append(
                f"({rule.layers[0]}.sized({threshold}.um) & {rule.layers[1]})"
                f".output(\"{rule.rule_id}\", \"{description}\")"
            )
        elif rule.family == "enclosure":
            lines.append(
                f"{rule.layers[0]}.enclosing({rule.layers[1]}, {threshold}.um)"
                f".output(\"{rule.rule_id}\", \"{description}\")"
            )
        elif rule.family == "overlap":
            lines.append(
                f"{rule.layers[0]}.overlap({rule.layers[1]}, {threshold}.um)"
                f".output(\"{rule.rule_id}\", \"{description}\")"
            )
        elif rule.family == "junction_min_area":
            layer = by_name[rule.layers[0]]
            # The ordinary min-area rule uses min_width^2. Junction min-area
            # may be tighter, so it needs a separate output category.
            if threshold != layer.min_width_um * layer.min_width_um:
                lines.append(
                    f"{rule.layers[0]}.with_area(nil, {threshold}.um2)"
                    f".output(\"{rule.rule_id}\", \"{description}\")"
                )
        else:
            raise ValueError(f"standalone backend has no emitter for {rule.family!r}")
    unsupported_standalone = sorted(
        {rule.family for rule in rules if rule.mandatory and "standalone" not in rule.supported_backends}
    )
    lines += [
        "",
        "# Rules this deck does NOT check, and which a clean run therefore does not",
        "# establish: " + ", ".join(sorted(set(UNSUPPORTED_RULES) | set(unsupported_standalone))) + ".",
        "",
    ]
    return "\n".join(lines)
