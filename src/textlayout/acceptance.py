"""Physics-fit acceptance evaluation.

A *benchmark* asks "does it draw?". An *acceptance test* asks the harder
question this project exists to answer:

    Does the generated layout meet the physical requirement, or does the
    system correctly refuse an infeasible requirement?

Every acceptance result reports an explicit position on the evidence ladder so a
geometry pass is never mistaken for a physics claim:

    1. geometry generated          (deterministic gdsfactory geometry exists)
    2. artifact generated          (GDS/SVG/JSON written)
    3. analytical estimate         (closed-form prediction from cited equations)
    4. solver input prepared       (open-source solver input files written)
    5. solver executed             (a real solver produced a non-empty output)
    6. extracted + compared        (a value parsed from solver output vs target)
    7. physics verified            (6 holds AND error within tolerance)
    8. fabrication ready           (process DRC + EM + expert review — never here)

`physics_verified` is *only* True when a solver executed, produced output, the
value was parsed, and it was compared against the target within tolerance. An
analytical estimate or a prepared solver input never sets it.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from textlayout import build_default_workflow
from textlayout.research import formulas as F
from textlayout.schemas.dsl import LayoutSpec
from textlayout.simulation import simulate_layout

# --- On-chip passive component limits (order-of-magnitude, with justification) -
# These are deliberately *generous* practical ceilings for a standard IC/RF
# process. They are used only to decide feasibility, not to size a device.
#   Spiral inductors: usable Q to ~10 nH; aggressive (large area, low Q) ~100 nH.
#   MIM/IDC capacitors at ~1-2 fF/um^2: practical to ~10 pF; aggressive ~100 pF.
# Refs: Mohan et al., IEEE JSSC 34(10) 1999 (spiral L); Bahl 2003 Ch. 2 (IDC C).
_L_MAX_COMFORTABLE_H = 10e-9
_C_MAX_COMFORTABLE_F = 100e-12
_L_MAX_AGGRESSIVE_H = 100e-9
_C_MAX_AGGRESSIVE_F = 100e-12


def _f0_lc(inductance_h: float, capacitance_f: float) -> float:
    """LC tank resonance f0 = 1 / (2*pi*sqrt(L*C))."""
    return 1.0 / (2.0 * math.pi * math.sqrt(inductance_h * capacitance_f))


def _required_lc(frequency_hz: float) -> float:
    """Required L*C product for an LC tank to resonate at ``frequency_hz``."""
    return 1.0 / (2.0 * math.pi * frequency_hz) ** 2


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    """Structured physics-fit verdict — pure data, JSON/Markdown serialisable."""

    name: str
    prompt: str
    verdict: str  # "INFEASIBLE" | "GEOMETRY_PASS" | "PHYSICS_VERIFIED"
    geometry_generated: bool = False
    artifact_generated: bool = False
    analytical_estimate: dict[str, Any] = field(default_factory=dict)
    solver_input_prepared: bool = False
    solver_executed: bool = False
    extracted_result: dict[str, Any] | None = None
    target_comparison: dict[str, Any] | None = None
    physics_verified: bool = False
    fabrication_ready: bool = False
    notes: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_ladder"] = {
            "geometry_generated": self.geometry_generated,
            "artifact_generated": self.artifact_generated,
            "analytical_estimate": bool(self.analytical_estimate),
            "solver_input_prepared": self.solver_input_prepared,
            "solver_executed": self.solver_executed,
            # Step 6 is a *solver* extraction+comparison; an analytical comparison
            # alone does not tick it.
            "extracted_and_compared": self.solver_executed and self.target_comparison is not None,
            "physics_verified": self.physics_verified,
            "fabrication_ready": self.fabrication_ready,
        }
        return data

    def to_markdown(self) -> str:
        lines = [
            f"# Acceptance — {self.name}",
            "",
            f"**Prompt:** {self.prompt}",
            "",
            f"**Verdict:** `{self.verdict}`",
            "",
            "## Evidence ladder",
            "",
        ]
        ladder = self.to_dict()["evidence_ladder"]
        for key, value in ladder.items():
            mark = "x" if value else " "
            lines.append(f"- [{mark}] {key.replace('_', ' ')}")
        lines.append("")
        if self.analytical_estimate:
            lines += ["## Analytical estimate", ""]
            lines += [f"- `{k}` = {v}" for k, v in self.analytical_estimate.items()]
            lines.append("")
        if self.target_comparison is not None:
            lines += ["## Target comparison", ""]
            lines += [f"- `{k}` = {v}" for k, v in self.target_comparison.items()]
            lines.append("")
        if self.notes:
            lines += ["## Notes", ""]
            lines += [f"- {n}" for n in self.notes]
            lines.append("")
        if self.alternatives:
            lines += ["## Alternatives", ""]
            lines += [f"- {a}" for a in self.alternatives]
            lines.append("")
        if self.references:
            lines += ["## References", ""]
            lines += [f"- {r}" for r in self.references]
            lines.append("")
        lines += [
            "## Status contract",
            "",
            "- `GEOMETRY_PASS` means geometry and artifacts are valid and an analytical",
            "  estimate exists — it is **not** a physics claim.",
            "- `PHYSICS_VERIFIED` requires a real solver run, a parsed result, and a",
            "  target comparison within tolerance.",
            "- No acceptance result is ever `fabrication_ready`.",
            "",
        ]
        return "\n".join(lines).rstrip() + "\n"


def evaluate_lc_resonator_feasibility(
    target_hz: float, *, name: str = "A_infeasible_5mhz_lc", prompt: str = ""
) -> AcceptanceResult:
    """Acceptance Test A — refuse an infeasible fully on-chip passive LC tank.

    First principles only: compute the required L*C, show no realistic on-chip
    L/C pairing reaches it, and report the minimum feasible on-chip frequency.
    No geometry, GDS, or SVG is produced — refusing to fake the layout is the
    pass condition.
    """
    required_lc = _required_lc(target_hz)
    f0_comfortable = _f0_lc(_L_MAX_COMFORTABLE_H, _C_MAX_COMFORTABLE_F)
    f0_aggressive = _f0_lc(_L_MAX_AGGRESSIVE_H, _C_MAX_AGGRESSIVE_F)
    required_l_for_100pf = required_lc / 100e-12
    lc_ratio = required_lc / (_L_MAX_AGGRESSIVE_H * _C_MAX_AGGRESSIVE_F)

    estimate = {
        "target_frequency_hz": target_hz,
        "required_LC_product_s2": required_lc,
        "best_comfortable_on_chip_f0_hz": f0_comfortable,
        "best_aggressive_on_chip_f0_hz": f0_aggressive,
        "required_L_for_C_100pF_H": required_l_for_100pf,
        "LC_shortfall_factor": lc_ratio,
    }
    feasible = target_hz >= f0_aggressive
    return AcceptanceResult(
        name=name,
        prompt=prompt or "Design a fully on-chip passive lumped LC resonator that reaches 5 MHz.",
        verdict="GEOMETRY_PASS" if feasible else "INFEASIBLE",
        analytical_estimate=estimate,
        notes=(
            f"Required L*C = {required_lc:.3e} s^2 to reach {target_hz / 1e6:.3g} MHz.",
            f"Most aggressive practical on-chip pairing (L={_L_MAX_AGGRESSIVE_H * 1e9:.0f} nH, "
            f"C={_C_MAX_AGGRESSIVE_F * 1e12:.0f} pF) resonates at "
            f"{f0_aggressive / 1e6:.1f} MHz — {lc_ratio:.0f}x short in the L*C product.",
            f"To hit {target_hz / 1e6:.3g} MHz with C=100 pF you would need "
            f"L={required_l_for_100pf * 1e6:.2f} uH, far beyond any on-chip spiral.",
            "No geometry, GDS, or SVG was generated; refusing to fake the layout is the pass.",
        ),
        alternatives=(
            "Off-chip discrete inductor and/or capacitor.",
            "Active gm-C / gyrator (synthetic inductor) realization.",
            "Mechanical / crystal / ceramic resonator.",
            f"Operate at a much higher frequency (>= {f0_comfortable / 1e6:.0f} MHz on-chip).",
        ),
        references=(
            "S. S. Mohan et al., IEEE JSSC 34(10), 1999 — on-chip spiral inductance limits.",
            "I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003.",
            "D. M. Pozar, 'Microwave Engineering', 4th ed., Wiley, 2012 — LCR resonance.",
        ),
    )


def evaluate_quarter_wave_resonator(
    frequency_ghz: float,
    *,
    name: str = "B_feasible_6ghz_resonator",
    prompt: str = "",
    technology: str = "generic_2metal",
    parameters: dict[str, Any] | None = None,
    execute_solver: bool = False,
    work_dir: str | Path | None = None,
) -> AcceptanceResult:
    """Acceptance Test B — feasible 6 GHz quarter-wave CPW resonator.

    Research first (vp = c/sqrt(eps_eff), L = vp/(4f)), build deterministic
    geometry, verify it, prepare the openEMS input, and — only when openEMS is
    actually executed and its resonance extracted and compared — promote to
    `PHYSICS_VERIFIED`. Otherwise the verdict stays `GEOMETRY_PASS` (Level 2).
    """
    workflow = build_default_workflow()
    tech = workflow.technology(technology)

    # Research first: compute the quarter-wave length from phase velocity, then
    # feed the *derived* length into the geometry — this is the whole point of
    # the test (physics drives geometry, not the other way around).
    eps_eff = F.cpw_eps_eff(tech.substrate_epsilon_r)
    v_p = F.SPEED_OF_LIGHT_M_PER_S / math.sqrt(eps_eff)
    length_um = F.cpw_quarter_wave_length_um(frequency_ghz, eps_eff)

    params = parameters or {
        "center_width_um": 10.0,
        "gap_um": 6.0,
        "coupling_gap_um": 6.0,
        "ground_width_um": 50.0,
        "metal": "M1",
    }
    params = {**params, "length_um": round(length_um, 4)}
    spec = LayoutSpec.model_validate(
        {
            "component": "QuarterWaveResonator",
            "technology": technology,
            "target": {"frequency_ghz": frequency_ghz},
            "parameters": params,
            "outputs": {"gds": True, "svg": True, "json": True},
        }
    )

    out = Path(work_dir) if work_dir is not None else None
    result = workflow.run(spec, formats=("gds", "svg", "json"), output_dir=out, stem="resonator")
    geometry_ok = result.report.passed
    has_ports = len(result.geometry.ports) >= 2

    estimate = {
        "target_frequency_ghz": frequency_ghz,
        "eps_eff": round(eps_eff, 4),
        "phase_velocity_m_per_s": round(v_p, 1),
        "predicted_quarter_wave_length_um": round(length_um, 2),
        "formula": "L = v_p / (4 f),  v_p = c / sqrt(eps_eff)",
        "port_count": len(result.geometry.ports),
    }

    simulation = simulate_layout(
        spec,
        result.geometry,
        tech,
        (out or Path(".")) / "simulation" if out else Path("."),
        solver="openems",
        execute=execute_solver,
    )
    solver_input_prepared = simulation.status in {"input_files_prepared", "executed"}
    solver_executed = simulation.status == "executed"

    extracted: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    physics_verified = False
    if solver_executed and simulation.extracted_quantities.get("resonance_frequency_ghz"):
        f_extracted = float(simulation.extracted_quantities["resonance_frequency_ghz"])
        extracted = {"resonance_frequency_ghz": f_extracted}
        error_pct = 100.0 * (f_extracted - frequency_ghz) / frequency_ghz
        comparison = {
            "target_ghz": frequency_ghz,
            "extracted_ghz": f_extracted,
            "error_pct": round(error_pct, 3),
            "tolerance_pct": 5.0,
        }
        physics_verified = abs(error_pct) <= 5.0

    notes = [
        f"Predicted length {length_um:.1f} um from L = v_p/(4f) at {frequency_ghz} GHz.",
        f"Geometry verification {'passed' if geometry_ok else 'FAILED'}; "
        f"{len(result.geometry.ports)} ports (signal + ground references).",
    ]
    if not solver_executed:
        notes.append(
            "openEMS input prepared but not executed — Level 2 only. "
            "PHYSICS_VERIFIED requires a solver run and an extracted resonance."
        )

    verdict = "PHYSICS_VERIFIED" if physics_verified else "GEOMETRY_PASS"
    return AcceptanceResult(
        name=name,
        prompt=prompt
        or (
            f"Design a {frequency_ghz:.0f} GHz quarter-wave CPW resonator on silicon with an "
            "estimated effective dielectric constant and output the predicted resonator length."
        ),
        verdict=verdict if geometry_ok else "GEOMETRY_FAIL",
        geometry_generated=geometry_ok and has_ports,
        artifact_generated=geometry_ok,
        analytical_estimate=estimate,
        solver_input_prepared=solver_input_prepared,
        solver_executed=solver_executed,
        extracted_result=extracted,
        target_comparison=comparison,
        physics_verified=physics_verified,
        notes=tuple(notes),
        references=(
            "R. N. Simons, 'Coplanar Waveguide Circuits, Components, and Systems', Wiley, 2001.",
            "D. M. Pozar, 'Microwave Engineering', 4th ed., Wiley, 2012 — quarter-wave theory.",
        ),
    )


def evaluate_idc_autosize(
    target_pf: float,
    *,
    name: str = "C_idc_autosize_0p6pf",
    prompt: str = "",
    technology: str = "generic_2metal",
    finger_width_um: float = 4.0,
    gap_um: float = 2.0,
    overlap_um: float = 250.0,
    reference_finger_pairs: int = 22,
    work_dir: str | Path | None = None,
) -> AcceptanceResult:
    """Acceptance Test C — auto-size IDC finger pairs to hit a capacitance target.

    Instead of keeping a fixed finger count, choose the finger-pair count whose
    Bahl/Alley estimate is closest to ``target_pf`` and show it reduces the
    target error versus the reference count. Analytical only unless a solver
    executes.
    """
    workflow = build_default_workflow()
    tech = workflow.technology(technology)
    eps_r = tech.substrate_epsilon_r

    def err(pairs: int) -> tuple[float, float]:
        est = F.idc_capacitance_pf(pairs, overlap_um, eps_r)
        return est, 100.0 * (est - target_pf) / target_pf

    # `idc_finger_pairs_for_target` returns the smallest count that *reaches* the
    # target (ceil). Acceptance instead picks the count with the smallest absolute
    # error, which may be one fewer — both are reported for transparency.
    smallest_reaching = F.idc_finger_pairs_for_target(target_pf, overlap_um, eps_r)
    search = range(max(1, smallest_reaching - 4), smallest_reaching + 5)
    best_pairs = min(search, key=lambda p: abs(err(p)[1]))
    best_est, best_err = err(best_pairs)
    ref_est, ref_err = err(reference_finger_pairs)
    reaching_est, reaching_err = err(smallest_reaching)

    spec = LayoutSpec.model_validate(
        {
            "component": "IDC",
            "technology": technology,
            "target": {"capacitance_pf": target_pf},
            "parameters": {
                "finger_pairs": best_pairs,
                "finger_width_um": finger_width_um,
                "gap_um": gap_um,
                "overlap_um": overlap_um,
                "bus_width_um": 25.0,
                "metal_layer": "M1",
            },
            "rules": {"min_width_um": 2.0, "min_gap_um": 2.0},
            "outputs": {"gds": True, "svg": True, "json": True},
        }
    )
    out = Path(work_dir) if work_dir is not None else None
    result = workflow.run(spec, formats=("gds", "svg", "json"), output_dir=out, stem="idc")
    geometry_ok = result.report.passed

    estimate = {
        "target_capacitance_pf": target_pf,
        "reference_finger_pairs": reference_finger_pairs,
        "reference_estimate_pf": round(ref_est, 4),
        "reference_error_pct": round(ref_err, 2),
        "chosen_finger_pairs": best_pairs,
        "chosen_estimate_pf": round(best_est, 4),
        "chosen_error_pct": round(best_err, 2),
        "smallest_count_reaching_target": smallest_reaching,
        "smallest_reaching_estimate_pf": round(reaching_est, 4),
        "smallest_reaching_error_pct": round(reaching_err, 2),
        "error_improvement_pct_points": round(abs(ref_err) - abs(best_err), 2),
        "model": "Bahl/Alley quasi-static IDC",
    }
    comparison = {
        "target_pf": target_pf,
        "analytical_pf": round(best_est, 4),
        "error_pct": round(best_err, 2),
        "method": "analytical",
        "solver_executed": False,
    }
    return AcceptanceResult(
        name=name,
        prompt=prompt
        or (
            f"Design an IDC targeting {target_pf} pF using {finger_width_um:g} um width, "
            f"{gap_um:g} um gap, and {overlap_um:g} um overlap. Choose the finger pair count "
            "automatically."
        ),
        verdict="GEOMETRY_PASS" if geometry_ok else "GEOMETRY_FAIL",
        geometry_generated=geometry_ok,
        artifact_generated=geometry_ok,
        analytical_estimate=estimate,
        solver_input_prepared=True,
        solver_executed=False,
        target_comparison=comparison,
        physics_verified=False,
        notes=(
            f"Auto-sized to {best_pairs} finger pairs "
            f"(|error| {abs(best_err):.2f}%) vs reference {reference_finger_pairs} "
            f"(|error| {abs(ref_err):.2f}%).",
            "Analytical (Bahl/Alley) only — no EM solver executed, so no EM-verified "
            "capacitance is claimed.",
        ),
        references=(
            "I. J. Bahl, 'Lumped Elements for RF and Microwave Circuits', Artech House, 2003, Ch. 2.",
            "G. D. Alley, IEEE Trans. MTT-18 (1970) 1028 — interdigital capacitor model.",
        ),
    )
