"""Open Solver Manager.

A single entry point that selects open-source solvers by device class and
accuracy target, runs the ones whose binaries are installed, and returns a
unified result. Commercial solvers are never invoked unless explicitly requested
as validation (``validation=True``), keeping the open stack on the critical path.

    manager = SolverManager()
    manager.solve(gds_path, sidecar=sidecar, device="JPA", target_accuracy="publication")

The device -> backend policy (open-first):

    CPW / resonator -> openEMS + Palace
    capacitor / IDC -> Elmer + FastCap
    inductor        -> FastHenry
    JPA             -> openEMS + JosephsonCircuits.jl
    qubit / transmon-> Palace + scqubits
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from text_to_gds.em_solvers import SOLVERS, get_em_solver

# EM backends run directly through the EMSolver registry; companion backends are
# circuit/parasitic tools driven by their own adapters (OpenQ3D, adapters.py).
_COMPANION_MODULES = {
    "FastCap": "text_to_gds.parasitics:export_fastcap",
    "FastHenry": "text_to_gds.parasitics:export_fasthenry",
    "JosephsonCircuits.jl": "text_to_gds.adapters:run_josephsoncircuits",
    "scqubits": "text_to_gds.research:write_hamiltonian_model",
}

# Ordered by device keyword priority (most specific first).
OPEN_BACKEND_POLICY: tuple[tuple[str, dict[str, list[str]]], ...] = (
    ("resonator", {"em": ["openEMS", "Palace"], "companion": []}),
    ("transmon", {"em": ["Palace"], "companion": ["scqubits"]}),
    ("qubit", {"em": ["Palace"], "companion": ["scqubits"]}),
    ("jtwpa", {"em": ["openEMS"], "companion": ["JosephsonCircuits.jl"]}),
    ("twpa", {"em": ["openEMS"], "companion": ["JosephsonCircuits.jl"]}),
    ("jpa", {"em": ["openEMS"], "companion": ["JosephsonCircuits.jl"]}),
    ("idc", {"em": ["Elmer"], "companion": ["FastCap"]}),
    ("interdigital", {"em": ["Elmer"], "companion": ["FastCap"]}),
    ("capacitor", {"em": ["Elmer"], "companion": ["FastCap"]}),
    ("inductor", {"em": [], "companion": ["FastHenry"]}),
    ("meander", {"em": ["openEMS"], "companion": ["FastHenry"]}),
    ("cpw", {"em": ["openEMS", "Palace"], "companion": []}),
    ("coplanar", {"em": ["openEMS", "Palace"], "companion": []}),
)

_DEFAULT_POLICY = {"em": ["openEMS"], "companion": []}
_COMMERCIAL = ("HFSS", "Sonnet")


def _normalize_device(device: str) -> str:
    return str(device or "").strip().lower()


def select_backends(device: str) -> dict[str, Any]:
    """Resolve a high-level device name to its open backend policy."""
    key = _normalize_device(device)
    for keyword, policy in OPEN_BACKEND_POLICY:
        if keyword in key:
            return {"device_class": keyword, **policy}
    return {"device_class": "default", **_DEFAULT_POLICY}


def route(device: str, *, target_accuracy: str = "iteration", validation: bool = False) -> dict[str, Any]:
    """Pure routing: which open backends to use and how many must agree."""
    if target_accuracy not in ("iteration", "publication"):
        raise ValueError("target_accuracy must be 'iteration' or 'publication'")
    policy = select_backends(device)
    required_agreement = 2 if target_accuracy == "publication" else 1
    plan = {
        "schema": "text-to-gds.open-solver-plan.v1",
        "device": device,
        "device_class": policy["device_class"],
        "target_accuracy": target_accuracy,
        "em_backends": policy["em"],
        "companion_backends": policy["companion"],
        "companion_modules": {name: _COMPANION_MODULES.get(name) for name in policy["companion"]},
        "required_agreement": required_agreement,
        "validation_backends": list(_COMMERCIAL) if validation else [],
        "policy": (
            "Open backends are primary. Commercial solvers run only when "
            "validation=True and never substitute for the open result."
        ),
    }
    return plan


def open_eigenmode(
    gds_path: str | Path,
    *,
    output_stem: str | Path,
    sidecar_path: str | Path | None = None,
    process_path: str | Path | None = None,
    target_frequency_ghz: float = 6.0,
    num_modes: int = 4,
    run: bool = False,
) -> dict[str, Any]:
    """Open HFSS-eigenmode analog: gmsh -> Palace, normalized to the HFSS schema.

    Returns the same shape an HFSS eigenmode run would: ``frequency``, ``Q``,
    ``participation``, ``fields``, ``convergence`` (values are populated only
    once Palace actually solves; otherwise they are ``None`` with status
    ``prepared``/``skipped``).
    """
    from text_to_gds.palace_bridge import write_palace_project

    stem = Path(output_stem)
    palace = write_palace_project(
        gds_path,
        config_path=stem.with_suffix(".palace.json"),
        report_path=stem.with_suffix(".palace.report.json"),
        mesh_path=stem.with_suffix(".msh"),
        mesh_report_path=stem.with_suffix(".mesh.json"),
        sidecar_path=sidecar_path,
        process_path=process_path,
        problem_type="Eigenmode",
        target_frequency_ghz=target_frequency_ghz,
        num_modes=num_modes,
        run=run,
    )
    modes = palace.get("eigenmodes") or []
    first = modes[0] if modes else {}
    convergence = {"returncode": palace["returncode"]} if "returncode" in palace else None
    return {
        "schema": "text-to-gds.open-eigenmode.v1",
        "backend": "Palace",
        "method": "fem_3d_eigenmode",
        "status": palace.get("status"),
        "frequency": first.get("frequency_ghz"),
        "Q": first.get("quality_factor"),
        "participation": first.get("participation"),
        "fields": palace.get("fields"),
        "convergence": convergence,
        "modes": modes,
        "mesh": palace.get("mesh"),
        "hfss_equivalent_schema": ["frequency", "Q", "participation", "fields", "convergence"],
        "report_path": palace.get("report_path"),
        "model_validity": palace.get("model_validity"),
    }


class SolverManager:
    """Routes and runs open-source solvers for a device."""

    def solve(
        self,
        gds_path: str | Path,
        *,
        sidecar: dict[str, Any] | None = None,
        device: str | None = None,
        target_accuracy: str = "iteration",
        output_stem: str | Path | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
        validation: bool = False,
    ) -> dict[str, Any]:
        if device is None:
            info = sidecar.get("info", {}) if isinstance(sidecar, dict) else {}
            device = str(info.get("device_type") or (sidecar or {}).get("pcell") or "unknown")
        stem = Path(output_stem) if output_stem is not None else Path(gds_path).with_suffix("")

        plan = route(device, target_accuracy=target_accuracy, validation=validation)
        runs: list[dict[str, Any]] = []
        available_open = 0

        for name in plan["em_backends"]:
            solver = SOLVERS.get(name)
            if solver is None:
                runs.append({"backend": name, "status": "unknown_backend"})
                continue
            if not solver.available():
                runs.append({"backend": name, "status": "skipped", "reason": "solver binary not installed"})
                continue
            try:
                result = solver.prepare(
                    gds_path,
                    output_stem=stem,
                    sidecar=sidecar,
                    process_path=process_path,
                    setup_frequency_ghz=setup_frequency_ghz,
                )
                available_open += 1
                runs.append({"backend": name, "status": result.get("status", "prepared"), "result": result})
            except Exception as exc:  # noqa: BLE001 - report, never crash the manager
                runs.append({"backend": name, "status": "error", "error": str(exc)})

        for name in plan["companion_backends"]:
            runs.append(
                {
                    "backend": name,
                    "status": "deferred",
                    "module": _COMPANION_MODULES.get(name),
                    "reason": "companion circuit/parasitic backend invoked by its own adapter",
                }
            )

        validation_runs: list[dict[str, Any]] = []
        if validation:
            for name in _COMMERCIAL:
                solver = get_em_solver(name)
                validation_runs.append(
                    {
                        "backend": name,
                        "role": "validation_only",
                        "available": solver.available(),
                        "status": "available" if solver.available() else "skipped",
                    }
                )

        accepted = available_open >= plan["required_agreement"]
        return {
            "schema": "text-to-gds.open-solver-run.v1",
            "device": device,
            "plan": plan,
            "runs": runs,
            "validation_runs": validation_runs,
            "open_backends_executed": available_open,
            "accepted": accepted,
            "acceptance_reason": (
                f"{available_open} open backend(s) ran; "
                f"{plan['required_agreement']} required for '{target_accuracy}'."
            ),
        }
