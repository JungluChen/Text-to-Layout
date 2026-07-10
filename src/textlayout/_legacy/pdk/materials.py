"""Superconducting material models for PDK-backed CAD generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Superconductor:
    name: str
    thickness_nm: float
    penetration_depth_nm: float
    sheet_inductance_ph_per_square: float
    critical_temperature_k: float


@dataclass(frozen=True)
class TunnelBarrier:
    name: str
    thickness_nm: float
    relative_permittivity: float
    specific_capacitance_ff_per_um2: float
    nominal_jc_ua_per_um2: float


@dataclass(frozen=True)
class Substrate:
    name: str
    thickness_um: float
    relative_permittivity: float
    loss_tangent: float


@dataclass(frozen=True)
class MaterialCatalog:
    nb: Superconductor
    al: Superconductor
    alox: TunnelBarrier
    si: Substrate

    def to_dict(self) -> dict[str, dict[str, float | str]]:
        return {
            "Nb": self.nb.__dict__,
            "Al": self.al.__dict__,
            "AlOx": self.alox.__dict__,
            "Si": self.si.__dict__,
        }


DEFAULT_MATERIAL_CATALOG = MaterialCatalog(
    nb=Superconductor(
        name="Nb",
        thickness_nm=180.0,
        penetration_depth_nm=90.0,
        sheet_inductance_ph_per_square=0.10,
        critical_temperature_k=9.2,
    ),
    al=Superconductor(
        name="Al",
        thickness_nm=60.0,
        penetration_depth_nm=50.0,
        sheet_inductance_ph_per_square=0.08,
        critical_temperature_k=1.2,
    ),
    alox=TunnelBarrier(
        name="AlOx",
        thickness_nm=2.0,
        relative_permittivity=9.0,
        specific_capacitance_ff_per_um2=45.0,
        nominal_jc_ua_per_um2=2.0,
    ),
    si=Substrate(
        name="high_resistivity_silicon",
        thickness_um=254.0,
        relative_permittivity=11.45,
        loss_tangent=1e-6,
    ),
)
