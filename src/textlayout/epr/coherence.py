"""Coherence estimation from energy participation ratios.

The math is standard and exact *given* the participations and loss tangents:

    1 / Q_total = Σ_i  p_i · tanδ_i
    T1          = Q_total / ω = Q_total / (2π f)

The uncertainty lives entirely in the inputs. When the participations come
from the analytical scaling backend, the absolute T1 number inherits its
order-of-magnitude confidence — the *ranking* of loss channels is more robust
than the absolute value, which is why the report leads with the dominant
channel and a sensitivity ranking rather than a single headline number.
"""

from __future__ import annotations

import math

from textlayout.epr.models import CoherenceEstimate, ParticipationRecord

_RECOMMENDATIONS: dict[str, str] = {
    "substrate": (
        "Bulk substrate loss dominates: use higher-resistivity substrate material "
        "or verify the bulk tanδ assumption with a witness resonator."
    ),
    "metal_substrate": (
        "Metal-substrate interface dominates: improve pre-deposition surface "
        "cleaning/etch, or widen gaps to reduce surface participation."
    ),
    "metal_air": (
        "Metal-air surface oxide dominates: consider post-processing (surface "
        "treatment, encapsulation) or geometry with lower edge participation."
    ),
    "substrate_air": (
        "Substrate-air surface layer dominates: improve post-etch cleaning or "
        "widen gaps to reduce the exposed-substrate participation."
    ),
    "junction_dielectric": (
        "Junction dielectric loss dominates: this is a process-level property of "
        "the tunnel barrier; smaller junction participation or a better barrier "
        "process is required."
    ),
}


def estimate_coherence(
    participations: list[ParticipationRecord], frequency_ghz: float
) -> CoherenceEstimate:
    """Combine per-channel participations into Q_total / T1 with a ranking.

    Raises ``ValueError`` when there are no participations or the total loss is
    zero — an estimate of infinite coherence is never reported.
    """
    if not participations:
        raise ValueError("cannot estimate coherence from zero participation records")
    if frequency_ghz <= 0:
        raise ValueError(f"frequency must be positive, got {frequency_ghz} GHz")

    losses = [(record, record.p_electric * record.tan_delta) for record in participations]
    total_inverse_q = sum(loss for _, loss in losses)
    if total_inverse_q <= 0.0:
        raise ValueError(
            "total participation-weighted loss is zero; refusing to claim infinite Q"
        )

    q_total = 1.0 / total_inverse_q
    omega = 2.0 * math.pi * frequency_ghz * 1e9  # rad/s
    t1_total_us = q_total / omega * 1e6

    ranked = sorted(losses, key=lambda item: item[1], reverse=True)
    dominant = ranked[0][0]
    ranking: list[dict[str, float | str]] = [
        {
            "region": record.region,
            "p_electric": record.p_electric,
            "tan_delta": record.tan_delta,
            "loss_fraction": loss / total_inverse_q,
        }
        for record, loss in ranked
    ]
    recommendation = _RECOMMENDATIONS.get(
        dominant.region,
        f"Loss channel {dominant.region!r} dominates; reduce its participation "
        "or its loss tangent first.",
    )
    return CoherenceEstimate(
        frequency_ghz=frequency_ghz,
        q_total=q_total,
        t1_total_us=t1_total_us,
        dominant_channel=dominant.region,
        sensitivity_ranking=ranking,
        recommendation=recommendation,
    )
