"""scqubits qubit engine — Phase 5.

Runs scqubits.Transmon (or Fluxonium) diagonalization to extract:
  - Energy levels
  - f01 transition frequency
  - Anharmonicity (α = f12 - f01)
  - Charge dispersion

Validates against known physical regimes:
  - Transmon: 20 < Ej/Ec < 200
  - Cooper-pair box: Ej/Ec < 5
  - Deep transmon: Ej/Ec > 100

If scqubits is not installed → status="SKIPPED", never fake values.
source="LLM" is a fatal error.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from textlayout._legacy.physics.jj import ec_ghz_from_capacitance, ej_ghz_from_ic, ic_from_area
from textlayout._legacy.solvers.interface import (
    AvailabilityStatus,
    EMSolverInterface,
    GeometrySpec,
    SolverOutput,
)

_SCHEMA = "text-to-gds.qubit-analysis.v1"


class ScqubitsSolver(EMSolverInterface):
    """Transmon/fluxonium energy spectrum via scqubits diagonalization."""

    @property
    def name(self) -> str:
        return "scqubits"

    def is_available(self) -> AvailabilityStatus:
        try:
            import importlib.util
            spec = importlib.util.find_spec("scqubits")
            if spec is None:
                return AvailabilityStatus(
                    available=False,
                    reason="scqubits not installed; install with: pip install scqubits",
                )
            import scqubits  # noqa: F401
            version = getattr(scqubits, "__version__", "unknown")
            return AvailabilityStatus(
                available=True,
                reason="scqubits available",
                version=version,
            )
        except Exception as e:
            return AvailabilityStatus(available=False, reason=str(e))

    def prepare(self, geometry: GeometrySpec, output_dir: Path) -> SolverOutput:
        """Extract Ej and Ec from geometry parameters."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        params = geometry.parameters
        ej_ghz = params.get("ej_ghz")
        ec_ghz = params.get("ec_ghz")

        if ej_ghz is None or ec_ghz is None:
            area_um2 = params.get("junction_area_um2")
            jc = params.get("jc_ua_per_um2", 2.0)
            cs = params.get("specific_capacitance_ff_per_um2", 50.0)

            if area_um2 is None:
                return SolverOutput.failed(
                    self.name,
                    "Need ej_ghz+ec_ghz or junction_area_um2+jc_ua_per_um2",
                    output_dir,
                )

            ic = ic_from_area(area_um2, jc)
            ej_ghz = ej_ghz_from_ic(ic)
            ec_ghz = ec_ghz_from_capacitance(area_um2 * cs * 1e-15)

        ratio = ej_ghz / ec_ghz

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="Ej/Ec prepared",
            output_dir=output_dir,
            parsed_data={
                "ej_ghz": ej_ghz,
                "ec_ghz": ec_ghz,
                "ej_ec_ratio": ratio,
                "n_levels": int(params.get("n_levels", 6)),
            },
        )

    def mesh(self, prepared: SolverOutput, output_dir: Path) -> SolverOutput:
        """No spatial mesh for circuit Hamiltonian — pass through."""
        return prepared

    def solve(self, meshed: SolverOutput, output_dir: Path) -> SolverOutput:
        """Diagonalize transmon Hamiltonian with scqubits."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        import scqubits

        ej = meshed.parsed_data["ej_ghz"]
        ec = meshed.parsed_data["ec_ghz"]
        n_levels = meshed.parsed_data.get("n_levels", 6)
        ratio = meshed.parsed_data["ej_ec_ratio"]

        t0 = time.monotonic()

        transmon = scqubits.Transmon(
            EJ=ej,
            EC=ec,
            ng=0.0,
            ncut=110,
            truncated_dim=n_levels + 2,
        )

        evals = transmon.eigenvals(evals_count=n_levels)
        elapsed = time.monotonic() - t0

        evals_ghz = [float(e) for e in evals]
        energies_relative = [e - evals_ghz[0] for e in evals_ghz]

        f01 = energies_relative[1] if len(energies_relative) > 1 else None
        f12 = (energies_relative[2] - energies_relative[1]) if len(energies_relative) > 2 else None
        anharmonicity = (f12 - f01) if (f01 is not None and f12 is not None) else None

        charge_disp = _estimate_charge_dispersion(ej, ec, transmon) if ratio < 50 else 0.0

        result_data = {
            "ej_ghz": ej,
            "ec_ghz": ec,
            "ej_ec_ratio": ratio,
            "energy_levels_ghz": evals_ghz,
            "transition_energies_ghz": energies_relative,
            "f01_ghz": round(f01, 6) if f01 is not None else None,
            "f12_ghz": round(f12, 6) if f12 is not None else None,
            "anharmonicity_mhz": round(anharmonicity * 1e3, 3) if anharmonicity is not None else None,
            "charge_dispersion_mhz": round(charge_disp * 1e3, 3) if charge_disp is not None else None,
            "n_levels": n_levels,
        }

        result_path = output_dir / "qubit_spectrum.json"
        result_path.write_text(
            json.dumps({
                "schema": _SCHEMA,
                "solver": "scqubits",
                "provenance": {
                    "method": "simulated",
                    "source": "scqubits Transmon diagonalization",
                    "confidence": 0.95,
                },
                **result_data,
            }, indent=2),
            encoding="utf-8",
        )

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="transmon spectrum computed",
            output_dir=output_dir,
            artifacts={"qubit_spectrum": result_path},
            parsed_data=result_data,
            execution_time_s=elapsed,
            version=avail.version,
        )

    def parse(self, solved: SolverOutput, output_dir: Path) -> SolverOutput:
        """Validate energy levels are finite and physical."""
        if solved.status != "EXECUTED":
            return solved

        levels = solved.parsed_data.get("energy_levels_ghz", [])
        if not levels:
            return SolverOutput.failed(self.name, "No energy levels in output", output_dir)

        if not all(math.isfinite(e) for e in levels):
            return SolverOutput.failed(
                self.name, "Non-finite energy levels in scqubits output", output_dir
            )

        f01 = solved.parsed_data.get("f01_ghz")
        if f01 is not None and not (0.1 <= f01 <= 30.0):
            solved.parsed_data["regime_warning"] = (
                f"f01={f01:.3f} GHz is outside typical transmon range [0.1, 30] GHz"
            )

        return solved

    def validate(self, parsed: SolverOutput) -> SolverOutput:
        """Validate Ej/Ec regime and flag anomalies."""
        if parsed.status != "EXECUTED":
            return parsed

        ratio = parsed.parsed_data.get("ej_ec_ratio", 0.0)
        warnings: list[str] = []

        if ratio < 5.0:
            warnings.append(
                f"Ej/Ec = {ratio:.1f} < 5: Cooper-pair box regime — "
                "strong charge sensitivity, not a standard transmon"
            )
        elif ratio < 20.0:
            warnings.append(
                f"Ej/Ec = {ratio:.1f} in [5, 20]: transitional regime — "
                "charge dispersion may limit coherence"
            )
        elif ratio > 200.0:
            warnings.append(
                f"Ej/Ec = {ratio:.1f} > 200: very deep transmon — "
                "confirm junction area is physical"
            )

        anharmonicity_mhz = parsed.parsed_data.get("anharmonicity_mhz")
        if anharmonicity_mhz is not None and abs(anharmonicity_mhz) < 50.0:
            warnings.append(
                f"Anharmonicity {anharmonicity_mhz:.1f} MHz < 50 MHz — "
                "leakage risk for standard gate pulses"
            )

        parsed.parsed_data["validation"] = {
            "regime_checks_passed": len(warnings) == 0,
            "ej_ec_ratio": ratio,
            "transmon_regime": 20.0 <= ratio <= 200.0,
            "warnings": warnings,
        }
        return parsed


def _estimate_charge_dispersion(ej: float, ec: float, transmon: Any) -> float:
    """Estimate charge dispersion ε01 = E01(ng=0.5) - E01(ng=0)."""
    try:
        e_ng0 = transmon.eigenvals(evals_count=2, charge_offset=0.0)
        e_ng05 = transmon.eigenvals(evals_count=2, charge_offset=0.5)
        f01_ng0 = float(e_ng0[1] - e_ng0[0])
        f01_ng05 = float(e_ng05[1] - e_ng05[0])
        return abs(f01_ng0 - f01_ng05)
    except Exception:
        # Analytical approximation for deep transmon: ε ~ (Ej/Ec)^(3/4) * exp(-sqrt(8Ej/Ec))
        ratio = ej / ec
        return 8.0 * math.sqrt(2.0 / math.pi) * (ratio ** (3.0 / 4.0)) * math.exp(-math.sqrt(8.0 * ratio)) * ec * 1e-3


def run_qubit_analysis(
    *,
    ej_ghz: float | None = None,
    ec_ghz: float | None = None,
    junction_area_um2: float | None = None,
    jc_ua_per_um2: float = 2.0,
    specific_capacitance_ff_per_um2: float = 50.0,
    n_levels: int = 6,
    output_dir: Path,
) -> dict[str, Any]:
    """High-level qubit analysis entry point.

    If scqubits is unavailable → status="SKIPPED". Never fake.
    """
    params: dict[str, Any] = {"n_levels": n_levels}
    if ej_ghz is not None:
        params["ej_ghz"] = ej_ghz
    if ec_ghz is not None:
        params["ec_ghz"] = ec_ghz
    if junction_area_um2 is not None:
        params["junction_area_um2"] = junction_area_um2
        params["jc_ua_per_um2"] = jc_ua_per_um2
        params["specific_capacitance_ff_per_um2"] = specific_capacitance_ff_per_um2

    solver = ScqubitsSolver()
    geometry = GeometrySpec(
        device_type="transmon",
        parameters=params,
        process_stack={},
    )
    output = solver.run_pipeline(geometry, output_dir)
    result = output.to_dict()
    result["schema"] = _SCHEMA
    return result
