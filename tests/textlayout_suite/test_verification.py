"""Verification framework tests (pass + fail paths)."""

from __future__ import annotations

from textlayout.generators import IDCGenerator
from textlayout.knowledge import GENERIC_2METAL
from textlayout.schemas.dsl import IDCSpec, LayoutSpec
from textlayout.verification import VerificationContext, default_verifier


def _ctx(spec_overrides: dict[str, object] | None = None, **param_overrides: object):
    base = dict(finger_pairs=22, finger_width_um=4, gap_um=2, overlap_um=250, bus_width_um=25)
    base.update(param_overrides)
    params = IDCSpec(**base)  # type: ignore[arg-type]
    geom = IDCGenerator().generate(params, GENERIC_2METAL, origin=(0.0, 0.0))
    spec = LayoutSpec(component="IDC", parameters=base, **(spec_overrides or {}))  # type: ignore[arg-type]
    return VerificationContext(spec=spec, params=params, geometry=geom, technology=GENERIC_2METAL)


def test_clean_idc_passes_all_checks() -> None:
    report = default_verifier().verify(_ctx())
    assert report.status == "pass"
    names = {c.name for c in report.checks}
    assert {"minimum_gap", "minimum_width", "finger_count_sanity", "ports_exist"} <= names


def test_gap_below_min_fails() -> None:
    report = default_verifier().verify(_ctx(gap_um=1.0))  # M1 min spacing = 2.0
    assert report.status == "fail"
    gap_check = next(c for c in report.checks if c.name == "minimum_gap")
    assert gap_check.status.value == "fail"
    assert report.errors


def test_unknown_layer_fails() -> None:
    report = default_verifier().verify(_ctx(metal_layer="M9"))
    assert report.status == "fail"
    layer_check = next(c for c in report.checks if c.name == "layer_exists")
    assert layer_check.status.value == "fail"


def test_report_dict_shape_matches_contract() -> None:
    doc = default_verifier().verify(_ctx()).to_dict()
    assert set(doc) == {"status", "component", "checks", "warnings", "errors"}
    gap = next(c for c in doc["checks"] if c["name"] == "minimum_gap")
    assert gap["value_um"] == 2.0
    assert gap["limit_um"] == 2.0
    assert gap["status"] == "pass"


def test_rules_override_min_gap() -> None:
    # Tighten the rule above the geometry's gap -> should now fail.
    report = default_verifier().verify(_ctx(spec_overrides={"rules": {"min_gap_um": 3.0}}))
    gap_check = next(c for c in report.checks if c.name == "minimum_gap")
    assert gap_check.limit == 3.0
    assert gap_check.status.value == "fail"


def test_rules_override_min_width() -> None:
    report = default_verifier().verify(
        _ctx(spec_overrides={"rules": {"min_width_um": 5.0}})
    )
    width_check = next(c for c in report.checks if c.name == "minimum_width")
    assert width_check.limit == 5.0
    assert width_check.status.value == "fail"
