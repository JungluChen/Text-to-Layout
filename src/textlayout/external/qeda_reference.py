"""Fixed independent custom-pad reference; not full QEDA integration acceptance."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from textlayout.external.qeda_module import decode_footprint_module

REFERENCE_ID = 'qeda-custom-two-pad-2026-10-23'
REFERENCE_SHA256 = '1f3ec346e676c97d09691845b71b34bbf3263d008671014f28fef9e5b1c7e427'
_TOLERANCE = Decimal('0.000001')


@dataclass(frozen=True)
class PadComparison:
    pad_number: int
    quantity: str
    actual_mm: float
    expected_mm: float
    absolute_error_mm: float
    within_tolerance: bool


@dataclass(frozen=True)
class PadReferenceAssessment:
    reference_id: str
    reference_sha256: str
    module_sha256: str
    absolute_tolerance_mm: float
    comparisons: tuple[PadComparison, ...]
    max_absolute_error_mm: float
    pad_reference_matches: bool


def assess_probe_pad_reference(data: bytes) -> PadReferenceAssessment:
    """Decode full Resistor_PROBERESISTOR then compare eight pad quantities.

    Fixed pre-execution reference: centres(-1.5,0)/(1.5,0) mm, size1x1.5 mm.
    Absolute tolerance1e-6 mm permits parsing roundoff, not a 0.001mm output
    quantization shift. No caller override. Structurally invalid data raises
    ValueError; valid geometry outside tolerance returns a mismatch. Decimal
    arithmetic makes threshold decisions independent of binary subtraction.
    No execution, symbol mapping, outline, mask margin, VRML or physical claim.
    """
    module = decode_footprint_module(data, expected_name='Resistor_PROBERESISTOR')
    comparisons = []
    for pad in sorted(module.pads, key=lambda p: p.number):
        expected = (-1.5 if pad.number == 1 else 1.5, 0.0, 1.0, 1.5)
        actual = (pad.x_mm, pad.y_mm, pad.width_mm, pad.height_mm)
        for quantity, observed, target in zip(('x', 'y', 'width', 'height'), actual, expected, strict=True):
            with localcontext(Context(prec=32)):
                error = abs(Decimal(str(observed)) - Decimal(str(target)))
            comparisons.append(PadComparison(
                pad_number=pad.number, quantity=quantity, actual_mm=observed,
                expected_mm=target, absolute_error_mm=float(error),
                within_tolerance=error <= _TOLERANCE,
            ))
    return PadReferenceAssessment(
        reference_id=REFERENCE_ID, reference_sha256=REFERENCE_SHA256,
        module_sha256=module.raw_sha256, absolute_tolerance_mm=float(_TOLERANCE),
        comparisons=tuple(comparisons),
        max_absolute_error_mm=max(c.absolute_error_mm for c in comparisons),
        pad_reference_matches=all(c.within_tolerance for c in comparisons),
    )
