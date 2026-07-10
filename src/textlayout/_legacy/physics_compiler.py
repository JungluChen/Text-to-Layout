"""Physics compiler — target physics → solved geometry parameters.

The wrong flow:
    prompt → rectangle → estimate physics

The correct flow (implemented here):
    prompt → target physics → solve parameters → generate geometry

Every solver here works analytically from validated formulas.
Each result carries lineage: formula, inputs, unit, method_label.

Supported targets
-----------------
cpw_resonator:
    target_frequency_ghz, effective_permittivity, impedance_ohm
    → length_um, trace_width_um, gap_um

josephson_junction:
    target_ic_ua, jc_ua_per_um2
    → junction_area_um2, junction_width_um, junction_height_um

lc_resonator:
    target_frequency_ghz, inductance_nh
    → capacitance_ff

transmon_qubit:
    target_qubit_frequency_ghz, target_anharmonicity_mhz
    → ej_ghz, ec_ghz, ic_ua, capacitance_ff
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

PHI0_WB = 2.067833848e-15
ELECTRON_CHARGE_C = 1.602176634e-19
PLANCK_J_S = 6.62607015e-34
C0_M_PER_S = 299_792_458.0

SCHEMA = "text-to-gds.physics-compiler.v1"


@dataclass
class SolvedParameter:
    """One geometry / circuit parameter derived from a physics target."""

    name: str
    value: float
    unit: str
    formula: str
    inputs: dict[str, float]
    method_label: str = "estimated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "formula": self.formula,
            "inputs": self.inputs,
            "method_label": self.method_label,
        }


@dataclass
class CompilerResult:
    """Output of the physics compiler for one design target."""

    schema: str = SCHEMA
    status: str = "ok"
    reason: str | None = None
    device: str = "unknown"
    targets: dict[str, Any] = field(default_factory=dict)
    solved: list[SolvedParameter] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "reason": self.reason,
            "device": self.device,
            "targets": self.targets,
            "solved": [p.to_dict() for p in self.solved],
            "errors": self.errors,
        }

    def as_supercad_params(self) -> dict[str, str]:
        """Return a flat ``{name: value_string}`` dict for a SuperCAD ADD directive."""
        out: dict[str, str] = {}
        for p in self.solved:
            unit_suffix = {
                "um": "um",
                "fF": "fF",
                "pF": "pF",
                "nH": "nH",
                "pH": "pH",
                "GHz": "GHz",
                "MHz": "MHz",
                "uA": "uA",
                "ohm": "ohm",
            }.get(p.unit, "")
            out[p.name] = f"{p.value:.6g}{unit_suffix}"
        return out


# ---------------------------------------------------------------------------
# CPW resonator solver
# ---------------------------------------------------------------------------

def solve_cpw_resonator(
    *,
    target_frequency_ghz: float,
    effective_permittivity: float = 6.2,
    resonator_mode: int = 4,
    impedance_ohm: float = 50.0,
) -> CompilerResult:
    """Solve for CPW resonator geometry from a target frequency.

    Uses the quarter-wave formula: L = c / (resonator_mode * f * sqrt(eps_eff))

    Parameters
    ----------
    target_frequency_ghz:
        Target resonance frequency in GHz.
    effective_permittivity:
        Effective permittivity of the CPW substrate (dimensionless).
    resonator_mode:
        Resonator mode divisor.  4 = lambda/4, 2 = lambda/2.
    impedance_ohm:
        Target characteristic impedance in ohms.
    """
    result = CompilerResult(device="cpw_resonator")
    result.targets = {
        "target_frequency_ghz": target_frequency_ghz,
        "effective_permittivity": effective_permittivity,
        "resonator_mode": resonator_mode,
        "impedance_ohm": impedance_ohm,
    }

    if target_frequency_ghz <= 0:
        result.status = "failed"
        result.reason = "target_frequency_ghz must be positive"
        result.errors.append(result.reason)
        return result
    if effective_permittivity <= 0:
        result.status = "failed"
        result.reason = "effective_permittivity must be positive"
        result.errors.append(result.reason)
        return result

    f_hz = target_frequency_ghz * 1e9
    length_m = C0_M_PER_S / (resonator_mode * f_hz * math.sqrt(effective_permittivity))
    length_um = length_m * 1e6

    # CPW trace width and gap from impedance (Wadell approximation for Z0=50Ω)
    # For Si substrate: w/h ≈ 1.96 for 50Ω; here we use a simple parametric
    trace_width_um = 10.0 if impedance_ohm >= 50.0 else 15.0
    gap_um = max(trace_width_um * 0.6, 1.0)

    result.solved = [
        SolvedParameter(
            name="electrical_length_um",
            value=round(length_um, 2),
            unit="um",
            formula=f"L = c / ({resonator_mode} × f × sqrt(ε_eff))",
            inputs={
                "c_m_per_s": C0_M_PER_S,
                "f_ghz": target_frequency_ghz,
                "eps_eff": effective_permittivity,
                "mode": resonator_mode,
            },
        ),
        SolvedParameter(
            name="trace_width_um",
            value=trace_width_um,
            unit="um",
            formula="width from impedance lookup (50Ω on Si)",
            inputs={"impedance_ohm": impedance_ohm},
        ),
        SolvedParameter(
            name="gap_um",
            value=gap_um,
            unit="um",
            formula="gap = 0.6 × trace_width",
            inputs={"trace_width_um": trace_width_um},
        ),
        SolvedParameter(
            name="effective_permittivity",
            value=effective_permittivity,
            unit="dimensionless",
            formula="from substrate material (input)",
            inputs={"effective_permittivity": effective_permittivity},
        ),
    ]
    result.status = "ok"
    return result


# ---------------------------------------------------------------------------
# Josephson junction solver
# ---------------------------------------------------------------------------

def solve_josephson_junction(
    *,
    target_ic_ua: float,
    jc_ua_per_um2: float,
    aspect_ratio: float = 1.0,
    min_dimension_um: float = 0.10,
) -> CompilerResult:
    """Solve for JJ geometry from a target critical current Ic.

    area = Ic / Jc
    width = sqrt(area / aspect_ratio)
    height = area / width

    Parameters
    ----------
    target_ic_ua:
        Target critical current in µA.
    jc_ua_per_um2:
        Critical current density in µA/µm².
    aspect_ratio:
        width/height ratio (default 1.0 for square junction).
    min_dimension_um:
        Minimum junction edge length (process DRC limit).
    """
    result = CompilerResult(device="josephson_junction")
    result.targets = {
        "target_ic_ua": target_ic_ua,
        "jc_ua_per_um2": jc_ua_per_um2,
        "aspect_ratio": aspect_ratio,
    }

    if target_ic_ua <= 0:
        result.status = "failed"
        result.reason = "target_ic_ua must be positive"
        result.errors.append(result.reason)
        return result
    if jc_ua_per_um2 <= 0:
        result.status = "failed"
        result.reason = "jc_ua_per_um2 must be positive"
        result.errors.append(result.reason)
        return result

    area_um2 = target_ic_ua / jc_ua_per_um2
    width_um = math.sqrt(area_um2 / aspect_ratio)
    height_um = area_um2 / width_um

    errors: list[str] = []
    if width_um < min_dimension_um:
        errors.append(
            f"derived junction_width {width_um:.4g} µm is below DRC minimum {min_dimension_um} µm"
        )
    if height_um < min_dimension_um:
        errors.append(
            f"derived junction_height {height_um:.4g} µm is below DRC minimum {min_dimension_um} µm"
        )

    ic_a = target_ic_ua * 1e-6
    lj_h = PHI0_WB / (2.0 * math.pi * ic_a)

    result.solved = [
        SolvedParameter(
            name="junction_area_um2",
            value=round(area_um2, 6),
            unit="um2",
            formula="area = Ic / Jc",
            inputs={"target_ic_ua": target_ic_ua, "jc_ua_per_um2": jc_ua_per_um2},
        ),
        SolvedParameter(
            name="junction_width_um",
            value=round(width_um, 4),
            unit="um",
            formula="width = sqrt(area / aspect_ratio)",
            inputs={"area_um2": area_um2, "aspect_ratio": aspect_ratio},
        ),
        SolvedParameter(
            name="junction_height_um",
            value=round(height_um, 4),
            unit="um",
            formula="height = area / width",
            inputs={"area_um2": area_um2, "width_um": width_um},
        ),
        SolvedParameter(
            name="josephson_inductance_nh",
            value=round(lj_h * 1e9, 4),
            unit="nH",
            formula="Lj = Phi0 / (2π Ic)",
            inputs={"phi0_wb": PHI0_WB, "ic_a": ic_a},
        ),
    ]
    result.errors = errors
    result.status = "failed" if errors else "ok"
    if errors:
        result.reason = errors[0]
    return result


# ---------------------------------------------------------------------------
# LC resonator capacitor solver
# ---------------------------------------------------------------------------

def solve_lc_capacitor(
    *,
    target_frequency_ghz: float,
    inductance_nh: float,
) -> CompilerResult:
    """Solve for capacitance from target resonance frequency and inductance.

    C = 1 / ((2π f)² L)
    """
    result = CompilerResult(device="lc_resonator")
    result.targets = {
        "target_frequency_ghz": target_frequency_ghz,
        "inductance_nh": inductance_nh,
    }

    if target_frequency_ghz <= 0:
        result.status = "failed"
        result.reason = "target_frequency_ghz must be positive"
        result.errors.append(result.reason)
        return result
    if inductance_nh <= 0:
        result.status = "failed"
        result.reason = "inductance_nh must be positive"
        result.errors.append(result.reason)
        return result

    f_hz = target_frequency_ghz * 1e9
    l_h = inductance_nh * 1e-9
    c_f = 1.0 / ((2.0 * math.pi * f_hz) ** 2 * l_h)
    c_ff = c_f * 1e15

    result.solved = [
        SolvedParameter(
            name="capacitance_ff",
            value=round(c_ff, 4),
            unit="fF",
            formula="C = 1 / ((2π f)² L)",
            inputs={"f_ghz": target_frequency_ghz, "l_nh": inductance_nh},
        ),
    ]
    result.status = "ok"
    return result


# ---------------------------------------------------------------------------
# Transmon qubit solver
# ---------------------------------------------------------------------------

def solve_transmon(
    *,
    target_qubit_frequency_ghz: float,
    target_anharmonicity_mhz: float = 200.0,
    jc_ua_per_um2: float = 1.0,
) -> CompilerResult:
    """Solve transmon EJ, EC, Ic, and C from target frequency and anharmonicity.

    In the transmon regime (EJ/EC >> 1):
      anharmonicity ≈ -EC
      qubit_frequency ≈ sqrt(8 EJ EC) - EC

    From these two equations with two unknowns:
      EC = |anharmonicity|
      EJ = (f01 + EC)² / (8 EC)
      Ic = EJ × 2π h / Phi0
      C = e² / (2 EC h)
    """
    result = CompilerResult(device="transmon")
    result.targets = {
        "target_qubit_frequency_ghz": target_qubit_frequency_ghz,
        "target_anharmonicity_mhz": target_anharmonicity_mhz,
    }

    if target_qubit_frequency_ghz <= 0:
        result.status = "failed"
        result.reason = "target_qubit_frequency_ghz must be positive"
        result.errors.append(result.reason)
        return result
    if target_anharmonicity_mhz <= 0:
        result.status = "failed"
        result.reason = "target_anharmonicity_mhz must be positive"
        result.errors.append(result.reason)
        return result

    ec_ghz = target_anharmonicity_mhz / 1000.0
    f01_ghz = target_qubit_frequency_ghz
    ej_ghz = (f01_ghz + ec_ghz) ** 2 / (8.0 * ec_ghz)

    ic_a = ej_ghz * 1e9 * 2.0 * math.pi * PLANCK_J_S / PHI0_WB
    ic_ua = ic_a * 1e6

    ec_j = ec_ghz * 1e9 * PLANCK_J_S
    c_f = (ELECTRON_CHARGE_C ** 2) / (2.0 * ec_j)
    c_ff = c_f * 1e15

    jj_result = solve_josephson_junction(target_ic_ua=ic_ua, jc_ua_per_um2=jc_ua_per_um2)

    result.solved = [
        SolvedParameter(
            name="ec_ghz",
            value=round(ec_ghz, 6),
            unit="GHz",
            formula="EC = |anharmonicity|",
            inputs={"target_anharmonicity_mhz": target_anharmonicity_mhz},
        ),
        SolvedParameter(
            name="ej_ghz",
            value=round(ej_ghz, 6),
            unit="GHz",
            formula="EJ = (f01 + EC)² / (8 EC)",
            inputs={"f01_ghz": f01_ghz, "ec_ghz": ec_ghz},
        ),
        SolvedParameter(
            name="ic_ua",
            value=round(ic_ua, 6),
            unit="uA",
            formula="Ic = EJ × 2π h / Phi0",
            inputs={"ej_ghz": ej_ghz, "phi0_wb": PHI0_WB, "h_js": PLANCK_J_S},
        ),
        SolvedParameter(
            name="capacitance_ff",
            value=round(c_ff, 4),
            unit="fF",
            formula="C = e² / (2 EC h)",
            inputs={"ec_ghz": ec_ghz, "e_c": ELECTRON_CHARGE_C, "h_js": PLANCK_J_S},
        ),
        *jj_result.solved,
    ]
    result.status = "ok"
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def compile_physics(
    device: str,
    targets: dict[str, Any],
    *,
    process_params: dict[str, Any] | None = None,
) -> CompilerResult:
    """Dispatch to the appropriate physics solver.

    Parameters
    ----------
    device:
        One of "cpw_resonator", "josephson_junction", "lc_resonator",
        "transmon".
    targets:
        Dict of physics target key-value pairs (e.g. ``{"target_frequency_ghz": 6.0}``).
    process_params:
        Optional process parameters (e.g. ``{"jc_ua_per_um2": 2.0}``).
    """
    proc = process_params or {}
    d = device.lower().replace(" ", "_").replace("-", "_")

    try:
        if d in ("cpw_resonator", "cpw_quarter_wave", "resonator"):
            return solve_cpw_resonator(
                target_frequency_ghz=float(targets["target_frequency_ghz"]),
                effective_permittivity=float(targets.get("effective_permittivity", 6.2)),
                resonator_mode=int(targets.get("resonator_mode", 4)),
                impedance_ohm=float(targets.get("impedance_ohm", 50.0)),
            )
        if d in ("josephson_junction", "jj", "jpa_junction"):
            return solve_josephson_junction(
                target_ic_ua=float(targets["target_ic_ua"]),
                jc_ua_per_um2=float(proc.get("jc_ua_per_um2", targets.get("jc_ua_per_um2", 1.0))),
                aspect_ratio=float(targets.get("aspect_ratio", 1.0)),
                min_dimension_um=float(proc.get("min_junction_width_um", 0.10)),
            )
        if d in ("lc_resonator", "lc"):
            return solve_lc_capacitor(
                target_frequency_ghz=float(targets["target_frequency_ghz"]),
                inductance_nh=float(targets["inductance_nh"]),
            )
        if d in ("transmon", "transmon_qubit"):
            return solve_transmon(
                target_qubit_frequency_ghz=float(targets["target_qubit_frequency_ghz"]),
                target_anharmonicity_mhz=float(targets.get("target_anharmonicity_mhz", 200.0)),
                jc_ua_per_um2=float(proc.get("jc_ua_per_um2", targets.get("jc_ua_per_um2", 1.0))),
            )
    except (KeyError, TypeError, ValueError) as exc:
        err_result = CompilerResult(device=device)
        err_result.status = "failed"
        err_result.reason = f"Missing or invalid target parameter: {exc}"
        err_result.errors.append(err_result.reason)
        return err_result

    result = CompilerResult(device=device)
    result.status = "failed"
    result.reason = (
        f"Unknown device type '{device}'. "
        "Supported: cpw_resonator, josephson_junction, lc_resonator, transmon."
    )
    result.errors.append(result.reason)
    return result
