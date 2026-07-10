"""Unified EM-solver abstraction and solver-priority routing.

Wraps the existing openEMS, PyAEDT/HFSS, and Sonnet bridges behind one
`EMSolver` interface and routes a device to the most appropriate backend:
planar superconducting structures (CPW, IDC, resonators) prefer Sonnet, full 3D
or packaging problems prefer HFSS, and the open-source default is openEMS.
"""

from __future__ import annotations

import shutil
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from textlayout._legacy.em_bridges import write_hfss_project_bridge, write_sonnet_project_bridge
from textlayout._legacy.research import write_openems_project


def _module_available(name: str) -> bool:
    """find_spec raises when a parent package is missing; treat that as unavailable."""
    try:
        return find_spec(name) is not None
    except ModuleNotFoundError:
        return False

PLANAR_KEYWORDS = (
    "cpw",
    "coplanar",
    "resonator",
    "idc",
    "interdigital",
    "capacitor",
    "meander",
    "transmission_line",
    "stwpa",
    "twpa",
)
VOLUMETRIC_KEYWORDS = (
    "package",
    "bondwire",
    "wirebond",
    "flip_chip",
    "airbridge",
    "cavity",
    "3d",
    "enclosure",
    "connector",
)


def _device_type(sidecar: dict[str, Any]) -> str:
    info = sidecar.get("info", {}) if isinstance(sidecar.get("info"), dict) else {}
    return str(info.get("device_type") or sidecar.get("pcell") or "unknown").lower()


def _geometry_class(device_type: str) -> str:
    if any(keyword in device_type for keyword in VOLUMETRIC_KEYWORDS):
        return "volumetric"
    if any(keyword in device_type for keyword in PLANAR_KEYWORDS):
        return "planar"
    return "lumped"


class EMSolver:
    """Common interface for an electromagnetic backend."""

    name: str = "em-solver"
    backend: str = ""
    method: str = ""
    open_source: bool = False
    license_required: bool = False
    best_for: tuple[str, ...] = ()
    notes: str = ""

    def available(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "backend": self.backend,
            "method": self.method,
            "open_source": self.open_source,
            "license_required": self.license_required,
            "best_for": list(self.best_for),
            "available": self.available(),
            "notes": self.notes,
        }

    def prepare(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar: dict[str, Any] | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
    ) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError


class OpenEMSSolver(EMSolver):
    name = "openEMS"
    backend = "openEMS EC-FDTD"
    method = "fdtd"
    open_source = True
    license_required = False
    best_for = ("open-source default", "CPW/microstrip extraction", "S-parameters", "E-field maps")
    notes = "Free FDTD. On Windows it runs through a dedicated Python 3.11 venv."

    def available(self) -> bool:
        if _module_available("openEMS"):
            return True
        tools_root = Path(__file__).resolve().parents[2] / ".tools"
        return (tools_root / "openems-venv").exists()

    def prepare(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar: dict[str, Any] | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
    ) -> dict[str, Any]:
        if sidecar is None:
            raise ValueError("openEMS preparation requires a sidecar dict")
        stem = Path(output_stem)
        return write_openems_project(
            sidecar,
            script_path=stem.with_suffix(".openems.py"),
            report_path=stem.with_suffix(".openems.json"),
            result_path=stem.with_suffix(".openems.result.json"),
            plot_path=stem.with_suffix(".openems.png"),
            target_frequency_ghz=setup_frequency_ghz,
            run=False,
        )


class HFSSSolver(EMSolver):
    name = "HFSS"
    backend = "Ansys HFSS via PyAEDT"
    method = "fem_3d"
    open_source = False
    license_required = True
    best_for = ("full 3D structures", "packaging", "eigenmode Q", "driven-modal S-parameters")
    notes = "Industry-standard 3D FEM; needs a licensed Ansys Electronics Desktop install."

    def available(self) -> bool:
        return _module_available("ansys.aedt.core")

    def prepare(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar: dict[str, Any] | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
    ) -> dict[str, Any]:
        stem = Path(output_stem)
        return write_hfss_project_bridge(
            gds_path,
            script_path=stem.with_suffix(".hfss.py"),
            report_path=stem.with_suffix(".hfss.json"),
            project_path=stem.with_suffix(".aedt"),
            setup_frequency_ghz=setup_frequency_ghz,
            process_path=process_path,
        )


class SonnetSolver(EMSolver):
    name = "Sonnet"
    backend = "Sonnet Suites via SonnetLab"
    method = "planar_mom"
    open_source = False
    license_required = True
    best_for = ("planar microwave", "CPW resonators", "interdigital capacitors", "thin-film loss")
    notes = "Method-of-moments planar solver; preferred for stratified planar superconducting layouts."

    def available(self) -> bool:
        return False

    def prepare(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar: dict[str, Any] | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
    ) -> dict[str, Any]:
        stem = Path(output_stem)
        return write_sonnet_project_bridge(
            gds_path,
            script_path=stem.with_suffix(".sonnet.m"),
            report_path=stem.with_suffix(".sonnet.json"),
            output_project_path=stem.with_suffix(".son"),
        )


class PalaceSolver(EMSolver):
    name = "Palace"
    backend = "Palace (AWS open-source FEM)"
    method = "fem_3d_eigenmode"
    open_source = True
    license_required = False
    best_for = ("eigenmode f0/Q", "field energy", "dielectric participation", "superconducting cavities")
    notes = "Open-source HFSS-eigenmode analog; C++/MPI FEM that solves under WSL/Linux."

    def available(self) -> bool:
        return shutil.which("palace") is not None

    def prepare(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar: dict[str, Any] | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
    ) -> dict[str, Any]:
        from textlayout._legacy.palace_bridge import write_palace_project

        stem = Path(output_stem)
        return write_palace_project(
            gds_path,
            config_path=stem.with_suffix(".palace.json"),
            report_path=stem.with_suffix(".palace.report.json"),
            mesh_path=stem.with_suffix(".msh"),
            mesh_report_path=stem.with_suffix(".mesh.json"),
            process_path=process_path,
            target_frequency_ghz=setup_frequency_ghz,
        )


class ElmerSolver(EMSolver):
    name = "Elmer"
    backend = "Elmer FEM (StatElecSolver)"
    method = "fem_electrostatic"
    open_source = True
    license_required = False
    best_for = ("capacitance matrix", "interdigital capacitors", "transmon pads", "Q3D analog")
    notes = "Open-source electrostatic FEM; the Q3D capacitance-matrix analog."

    def available(self) -> bool:
        return any(shutil.which(name) for name in ("ElmerSolver", "ElmerSolver_mpi", "elmersolver"))

    def prepare(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar: dict[str, Any] | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
    ) -> dict[str, Any]:
        from textlayout._legacy.elmer_bridge import write_elmer_project

        stem = Path(output_stem)
        return write_elmer_project(
            gds_path,
            sif_path=stem.with_suffix(".sif"),
            report_path=stem.with_suffix(".elmer.report.json"),
            mesh_path=stem.with_suffix(".msh"),
            mesh_report_path=stem.with_suffix(".mesh.json"),
            process_path=process_path,
        )


class MeepSolver(EMSolver):
    name = "MEEP"
    backend = "MEEP FDTD (MIT)"
    method = "fdtd"
    open_source = True
    license_required = False
    best_for = ("field/photonics FDTD", "dispersion", "field maps", "optical and microwave")
    notes = "Open-source FDTD; runs when the meep Python package is importable (Linux/conda)."

    def available(self) -> bool:
        from textlayout._legacy.meep_bridge import meep_available

        return meep_available()

    def prepare(
        self,
        gds_path: str | Path,
        *,
        output_stem: str | Path,
        sidecar: dict[str, Any] | None = None,
        process_path: str | Path | None = None,
        setup_frequency_ghz: float = 6.0,
    ) -> dict[str, Any]:
        from textlayout._legacy.meep_bridge import write_meep_project

        stem = Path(output_stem)
        return write_meep_project(
            gds_path,
            script_path=stem.with_suffix(".meep.py"),
            report_path=stem.with_suffix(".meep.json"),
            target_frequency_ghz=setup_frequency_ghz,
            run=False,
        )


SOLVERS: dict[str, EMSolver] = {
    solver.name: solver
    for solver in (
        OpenEMSSolver(),
        HFSSSolver(),
        SonnetSolver(),
        PalaceSolver(),
        ElmerSolver(),
        MeepSolver(),
    )
}

# Open-source-first priority: every open backend ranks strictly above every
# commercial backend. Commercial solvers (HFSS/Sonnet) are validation-only and
# are never recommended as the primary solver. Within each tier, ordering still
# follows typical geometric suitability.
_SCORES: dict[str, dict[str, float]] = {
    "planar": {"openEMS": 1.0, "Palace": 0.85, "MEEP": 0.7, "Elmer": 0.6, "Sonnet": 0.45, "HFSS": 0.4},
    "volumetric": {"Palace": 1.0, "openEMS": 0.8, "MEEP": 0.6, "Elmer": 0.55, "HFSS": 0.45, "Sonnet": 0.3},
    "lumped": {"openEMS": 0.95, "Palace": 0.8, "MEEP": 0.65, "Elmer": 0.6, "HFSS": 0.45, "Sonnet": 0.4},
}

_REASONS: dict[str, str] = {
    "planar": "stratified planar geometry handled by the open FDTD/FEM stack (openEMS, then Palace)",
    "volumetric": "true 3D / packaging geometry handled by the open 3D FEM stack (Palace, then openEMS)",
    "lumped": "lumped/unknown geometry defaults to the open-source EM backend",
}


def list_em_solvers() -> list[dict[str, Any]]:
    """Return metadata and local availability for every EM backend."""
    return [solver.to_dict() for solver in SOLVERS.values()]


def get_em_solver(name: str) -> EMSolver:
    """Look up an EM solver by case-insensitive name."""
    for key, solver in SOLVERS.items():
        if key.lower() == name.lower():
            return solver
    raise ValueError(f"Unknown EM solver: {name}")


def recommend_em_solver(sidecar: dict[str, Any]) -> dict[str, Any]:
    """Rank EM solvers for a device and recommend one by solver-priority routing."""
    device_type = _device_type(sidecar)
    geometry_class = _geometry_class(device_type)
    scores = _SCORES[geometry_class]
    ranking = []
    for name, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        solver = SOLVERS[name]
        ranking.append(
            {
                "solver": name,
                "score": score,
                "available": solver.available(),
                "open_source": solver.open_source,
                "role": "primary" if solver.open_source else "validation_only",
                "method": solver.method,
                "reason": _REASONS[geometry_class],
            }
        )
    recommended = next(entry["solver"] for entry in ranking if entry["open_source"])
    return {
        "schema": "text-to-gds.em-solver-routing.v1",
        "device_type": device_type,
        "geometry_class": geometry_class,
        "recommended": recommended,
        "recommended_open_source": True,
        "ranking": ranking,
        "model_validity": (
            "Open-source-first routing from device geometry class. Open backends are "
            "always preferred; commercial backends (HFSS/Sonnet) are validation-only "
            "and never recommended as primary. Any backend can run any structure."
        ),
    }
