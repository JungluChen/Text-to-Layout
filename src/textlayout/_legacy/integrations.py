from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from textlayout._paths import repository_root

PROJECT_ROOT = repository_root()
LOCAL_TOOLS_ROOT = Path(os.environ.get("TEXT_TO_GDS_TOOLS", PROJECT_ROOT / ".tools")).resolve()


@dataclass(frozen=True)
class ResearchIntegration:
    id: str
    name: str
    source_url: str
    purpose: str
    text_to_gds_role: str
    local_kind: str
    python_module: str | None
    executable: str | None
    installed: bool
    resolved_path: str | None
    install_hint: str
    output_artifacts: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _module_path(module_name: str | None) -> str | None:
    if module_name is None:
        return None
    try:
        spec = find_spec(module_name)
    except ModuleNotFoundError:
        return None
    return spec.origin if spec is not None else None


def _candidate_paths(executable: str) -> list[Path]:
    normalized = Path(executable).name.lower()
    candidates: list[Path] = []
    env_key = {
        "julia": "TEXT_TO_GDS_JULIA",
        "openems": "TEXT_TO_GDS_OPENEMS",
        "openems.exe": "TEXT_TO_GDS_OPENEMS",
    }.get(normalized)
    if env_key and os.environ.get(env_key):
        candidates.append(Path(os.environ[env_key]))
    if normalized == "julia":
        candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("julia-*/bin/julia.exe"), reverse=True))
        candidates.append(LOCAL_TOOLS_ROOT / "julia" / "bin" / "julia.exe")
    if normalized in {"openems", "openems.exe"}:
        candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("openEMS*/bin/openEMS.exe"), reverse=True))
        candidates.append(LOCAL_TOOLS_ROOT / "openEMS" / "bin" / "openEMS.exe")
    return candidates


def _executable_path(executable: str | None) -> str | None:
    if executable is None:
        return None
    literal = Path(executable)
    if literal.exists():
        return str(literal.resolve())
    from_path = shutil.which(executable)
    if from_path is not None:
        return from_path
    for candidate in _candidate_paths(executable):
        if candidate.exists():
            return str(candidate.resolve())
    return None


def _installed(module: str | None, executable: str | None) -> tuple[bool, str | None]:
    module_path = _module_path(module)
    executable_path = _executable_path(executable)
    return module_path is not None or executable_path is not None, module_path or executable_path


def _entry(
    *,
    id: str,
    name: str,
    source_url: str,
    purpose: str,
    text_to_gds_role: str,
    local_kind: str,
    python_module: str | None,
    executable: str | None = None,
    install_hint: str,
    output_artifacts: list[str],
    notes: list[str],
) -> ResearchIntegration:
    installed, resolved_path = _installed(python_module, executable)
    return ResearchIntegration(
        id=id,
        name=name,
        source_url=source_url,
        purpose=purpose,
        text_to_gds_role=text_to_gds_role,
        local_kind=local_kind,
        python_module=python_module,
        executable=executable,
        installed=installed,
        resolved_path=resolved_path,
        install_hint=install_hint,
        output_artifacts=output_artifacts,
        notes=notes,
    )


def list_research_integrations() -> list[dict[str, Any]]:
    """Return optional research tool integrations distilled into local adapter roles."""
    integrations = [
        _entry(
            id="gdsfactory",
            name="gdsfactory",
            source_url="https://github.com/gdsfactory/gdsfactory",
            purpose="Python component/PCell layout generation, PDKs, regression-ready GDS flows",
            text_to_gds_role="Primary layout engine for trusted PCells and GDS writing.",
            local_kind="python_module",
            python_module="gdsfactory",
            install_hint="Installed by the core Text-to-GDS dependency set.",
            output_artifacts=[".gds", ".sidecar.json", ".layout.png"],
            notes=["Keep GDS as the source of truth; treat screenshots and CAD files as views."],
        ),
        _entry(
            id="josephsoncircuits",
            name="JosephsonCircuits.jl",
            source_url="https://github.com/kpobrien/JosephsonCircuits.jl",
            purpose="Frequency-domain multi-tone harmonic balance for nonlinear Josephson circuits",
            text_to_gds_role=(
                "External Julia adapter for JPA/JTWPA gain, S-parameters, pump response, "
                "and future noise analysis."
            ),
            local_kind="external_julia",
            python_module=None,
            executable="julia",
            install_hint=(
                "Run scripts/install_toolchain.ps1 -InstallJulia, then add "
                "JosephsonCircuits.jl in the local Julia depot."
            ),
            output_artifacts=[".josephsoncircuits.jl", ".josephsoncircuits.json"],
            notes=["Current generated model is a lumped starter, not EM/extracted signoff."],
        ),
        _entry(
            id="scikit-rf",
            name="scikit-rf",
            source_url="https://github.com/scikit-rf/scikit-rf",
            purpose="RF network, Touchstone, S-parameter, Smith chart, and calibration analysis",
            text_to_gds_role="Optional backend for reading exported .s2p data and future RF plots.",
            local_kind="python_module",
            python_module="skrf",
            install_hint="Install with: py -3 -m uv sync --extra rf",
            output_artifacts=[".s2p", ".rf.json", ".rf.png", ".rf.csv"],
            notes=["Magnitude-only exports use zero phase until an adapter supplies complex S-data."],
        ),
        _entry(
            id="openems",
            name="openEMS",
            source_url="https://github.com/thliebig/openEMS",
            purpose="Open-source EC-FDTD EM simulation with Python/Octave/Matlab scripting",
            text_to_gds_role="Generated CPW/resonator EM project handoff for Z0 and field maps.",
            local_kind="external_em",
            python_module="openEMS",
            executable="openEMS",
            install_hint=(
                "Install openEMS and CSXCAD separately, then set TEXT_TO_GDS_OPENEMS if the "
                "executable is outside PATH."
            ),
            output_artifacts=[".openems.py", ".openems.json", "E-field.vtk", "Z0.json"],
            notes=["The generated script is a handoff scaffold until calibrated ports are extracted."],
        ),
        _entry(
            id="optuna",
            name="Optuna",
            source_url="https://github.com/optuna/optuna",
            purpose="Define-by-run hyperparameter optimization with studies and trials",
            text_to_gds_role="Optional optimizer backend for gain/bandwidth/P1dB constrained sweeps.",
            local_kind="python_module",
            python_module="optuna",
            install_hint="Install with: py -3 -m uv sync --extra optimization",
            output_artifacts=[".optuna.json", ".optuna.csv", ".optuna.png"],
            notes=["Falls back to a deterministic local grid if Optuna is absent."],
        ),
        _entry(
            id="qiskit-metal",
            name="Quantum Metal / Qiskit Metal",
            source_url="https://github.com/qiskit-community/qiskit-metal",
            purpose="Superconducting quantum chip component, renderer, and analysis architecture",
            text_to_gds_role=(
                "Architecture bridge: PCell -> geometry -> renderer -> simulation metadata."
            ),
            local_kind="python_module",
            python_module="qiskit_metal",
            install_hint="Install with: py -3 -m uv sync --extra metal",
            output_artifacts=[".qmetal.json", ".qmetal.py"],
            notes=["Bridge files document mapping; Text-to-GDS remains gdsfactory/GDS-first."],
        ),
        _entry(
            id="scqubits",
            name="scqubits",
            source_url="https://github.com/scqubits/scqubits",
            purpose="Superconducting qubit Hamiltonians, spectra, matrix elements, and sweeps",
            text_to_gds_role="Optional Hamiltonian-model handoff from layout-derived JJ/SQUID values.",
            local_kind="python_module",
            python_module="scqubits",
            install_hint="Install with: py -3 -m uv sync --extra quantum",
            output_artifacts=[".hamiltonian.json", ".scqubits.py"],
            notes=["Layout-derived EJ/EC is a starter model until capacitance extraction is calibrated."],
        ),
        _entry(
            id="qcodes",
            name="QCoDeS",
            source_url="https://github.com/microsoft/Qcodes",
            purpose="Python measurement automation, instrument control, and experiment databases",
            text_to_gds_role="Measurement-plan export for VNA, pump, flux-bias, and fridge sweeps.",
            local_kind="python_module",
            python_module="qcodes",
            install_hint="Install with: py -3 -m uv sync --extra measurement",
            output_artifacts=[".measurement.json", ".qcodes.py"],
            notes=["Generated scripts are lab handoff templates; no instruments are touched locally."],
        ),
        _entry(
            id="pyepr",
            name="pyEPR",
            source_url="https://github.com/zlatko-minev/pyEPR",
            purpose="Energy-participation extraction and Josephson-circuit quantization",
            text_to_gds_role="HFSS field-energy to junction/dielectric participation, chi, anharmonicity, and T1 handoff.",
            local_kind="python_module_external_hfss",
            python_module="pyEPR",
            install_hint="Install with: py -3 -m uv sync --extra epr",
            output_artifacts=[".epr.json", ".pyepr.py"],
            notes=["DistributedAnalysis requires solved HFSS fields; numerical analysis can use exported energies."],
        ),
        _entry(
            id="hfss",
            name="Ansys HFSS and Q3D / PyAEDT",
            source_url="https://github.com/ansys/pyaedt",
            purpose="Industrial 3D EM eigenmode, driven-modal, and capacitance extraction",
            text_to_gds_role=(
                "Process-mapped HFSS/Q3D project scripts, S-parameters, fields, and matrices."
            ),
            local_kind="python_module_proprietary_solver",
            python_module="ansys.aedt.core",
            install_hint="Install with: py -3 -m uv sync --extra hfss and provide licensed AEDT.",
            output_artifacts=[
                ".pyaedt.config.json",
                ".hfss.py",
                ".q3d.py",
                ".aedt",
                ".s2p",
                ".q3d.matrix.csv",
                ".Efield.png",
            ],
            notes=[
                "Generated ports and default PEC/copper conductors require review before signoff."
            ],
        ),
        _entry(
            id="sonnet",
            name="Sonnet Suites / SonnetLab",
            source_url="https://www.sonnetsoftware.com/",
            purpose="Planar electromagnetic simulation used in microwave IC design",
            text_to_gds_role="Generated SonnetLab GDS import and frequency-sweep script.",
            local_kind="external_proprietary_em",
            python_module=None,
            executable="sonnet",
            install_hint="Install Sonnet Suites and SonnetLab, then expose the Sonnet executable.",
            output_artifacts=[".sonnet.m", ".sonnet.json", ".son"],
            notes=["No solver execution occurs when Sonnet is unavailable."],
        ),
    ]
    return [integration.to_dict() for integration in integrations]
