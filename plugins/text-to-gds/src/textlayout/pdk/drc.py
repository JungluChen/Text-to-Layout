"""PDK-level DRC hooks: min width/spacing/layer-existence (from the layer
stack itself) plus a density-rule placeholder foundry decks always carry.

Min width, min spacing, and layer existence are already enforced by
:mod:`textlayout.verification.checks` against the projected ``Technology`` —
this module adds the one check a ``Technology`` cannot express: **density**,
which requires knowing the filled area of a window, not just a single
polygon's dimensions. It is a placeholder (a single fill-fraction number in,
a pass/fail out) — a real density/antenna deck tiles the layout and checks
every window; wiring that tiling is future work (see docs/pdk_abstraction.md).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from textlayout.pdk.models import PDK


class DensityCheckResult(BaseModel):
    """Result of one density-rule check against a PDK layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: str
    filled_fraction: float = Field(ge=0.0, le=1.0)
    min_required: float | None
    max_allowed: float | None
    passed: bool
    message: str


def check_layer_exists(pdk: PDK, layer_name: str) -> bool:
    """True when ``layer_name`` is defined in this PDK."""
    return layer_name in pdk.layer_names()


def check_density(pdk: PDK, layer_name: str, filled_fraction: float) -> DensityCheckResult:
    """Check one layer's fill fraction against the PDK's density placeholder rule.

    ``filled_fraction`` must be computed by the caller (e.g. drawn area / window
    area for one density-check window) — this function only evaluates the rule.
    A layer with no density rule configured always passes (nothing to check).
    """
    if not 0.0 <= filled_fraction <= 1.0:
        raise ValueError(f"filled_fraction must be in [0, 1], got {filled_fraction}")
    layer = pdk.layer(layer_name)
    min_required = layer.min_density_fraction
    max_allowed = layer.max_density_fraction
    if min_required is None and max_allowed is None:
        return DensityCheckResult(
            layer=layer_name,
            filled_fraction=filled_fraction,
            min_required=None,
            max_allowed=None,
            passed=True,
            message=f"{layer_name} has no configured density rule; check is a no-op.",
        )
    too_sparse = min_required is not None and filled_fraction < min_required
    too_dense = max_allowed is not None and filled_fraction > max_allowed
    passed = not (too_sparse or too_dense)
    if passed:
        message = f"{layer_name} density {filled_fraction:.3f} within configured bounds."
    elif too_sparse:
        message = f"{layer_name} density {filled_fraction:.3f} below minimum {min_required:.3f}."
    else:
        message = f"{layer_name} density {filled_fraction:.3f} above maximum {max_allowed:.3f}."
    return DensityCheckResult(
        layer=layer_name,
        filled_fraction=filled_fraction,
        min_required=min_required,
        max_allowed=max_allowed,
        passed=passed,
        message=message,
    )
