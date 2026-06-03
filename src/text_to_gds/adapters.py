from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from typing import Any

from text_to_gds.simulation import critical_current_ua, josephson_inductance_ph


@dataclass(frozen=True)
class SimulationAdapter:
    name: str
    executable: str
    purpose: str
    mode: str
    source_url: str
    install_hint: str
    installed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_simulation_adapters() -> list[dict[str, Any]]:
    """Report local availability of supported superconducting simulators."""
    adapters = [
        SimulationAdapter(
            name="JosephsonCircuits.jl",
            executable="julia",
            purpose="frequency-domain multi-tone harmonic balance, gain, S-parameters, noise",
            mode="external_julia",
            source_url="https://github.com/kpobrien/JosephsonCircuits.jl",
            install_hint=(
                'Install Julia, then run: julia -e "using Pkg; '
                "Pkg.add(url=\\\"https://github.com/kpobrien/JosephsonCircuits.jl\\\")\""
            ),
            installed=shutil.which("julia") is not None,
        ),
        SimulationAdapter(
            name="JoSIM",
            executable="josim",
            purpose="SPICE-like superconducting transient simulation using the RCSJ JJ model",
            mode="external_cli",
            source_url="https://github.com/JoeyDelp/JoSIM",
            install_hint="Install a JoSIM release binary and ensure josim is on PATH.",
            installed=shutil.which("josim") is not None,
        ),
    ]
    return [adapter.to_dict() for adapter in adapters]


def select_adapter(name: str) -> dict[str, Any]:
    normalized = name.lower().replace(" ", "").replace("-", "").replace("_", "")
    for adapter in list_simulation_adapters():
        candidate = adapter["name"].lower().replace(" ", "").replace("-", "").replace("_", "")
        if normalized in {candidate, adapter["mode"]}:
            return adapter
    raise ValueError(f"Unknown simulator adapter: {name}")


def josim_netlist_from_sidecar(
    sidecar: dict[str, Any],
    *,
    jc_ua_per_um2: float,
    shunt_capacitance_ff: float,
    stop_time_ps: float = 200.0,
    timestep_ps: float = 1.0,
) -> str:
    """Create a minimal JoSIM-compatible transient deck for the extracted JJ."""
    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = critical_current_ua(area_um2, jc_ua_per_um2)
    cap_f = shunt_capacitance_ff * 1e-15
    return "\n".join(
        [
            "* Text-to-GDS generated JoSIM starter deck",
            f".PARAM IC={ic_ua * 1e-6:.12g}",
            f".PARAM CSH={cap_f:.12g}",
            "IIN in 0 PULSE(0 1u 0 1p 1p 20p 50p)",
            "BJJ in 0 jjmod AREA=1",
            "CSH in 0 {CSH}",
            ".MODEL jjmod JJ(RTYPE=1, VG=2.8m, DELV=0.08m, IC={IC}, RN=10, CAP=0)",
            f".TRAN {timestep_ps:.12g}p {stop_time_ps:.12g}p",
            ".PRINT DEVV BJJ",
            ".END",
        ]
    )


def josephsoncircuits_plan_from_sidecar(
    sidecar: dict[str, Any],
    *,
    target_frequency_ghz: float | None,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float | None = None,
) -> dict[str, Any]:
    """Return the command/data plan for a future JosephsonCircuits.jl run."""
    info = sidecar.get("info", {})
    area_um2 = float(info.get("junction_area_um2", 0.0))
    ic_ua = float(info.get("critical_current_ua", 0.0))
    if not ic_ua and area_um2:
        ic_ua = critical_current_ua(area_um2, jc_ua_per_um2=1.0)
    lj_ph = josephson_inductance_ph(ic_ua) if ic_ua else None
    return {
        "adapter": select_adapter("JosephsonCircuits.jl"),
        "target_frequency_ghz": target_frequency_ghz,
        "target_gain_db": target_gain_db,
        "target_bandwidth_mhz": target_bandwidth_mhz,
        "layout_derived_parameters": {
            "junction_area_um2": area_um2,
            "critical_current_ua_at_1ua_per_um2": ic_ua,
            "josephson_inductance_ph_at_1ua_per_um2": lj_ph,
            "ports": sidecar.get("ports", []),
        },
        "next_files": {
            "julia_script": "workspace/artifacts/<name>.josephsoncircuits.jl",
            "simulation_json": "workspace/artifacts/<name>.josephsoncircuits.json",
        },
        "notes": [
            "This adapter is intentionally a command plan until Julia and JosephsonCircuits.jl "
            "are installed locally.",
            "Use layout-extracted JJ, CPW, coupling, and shunt parameters to build the harmonic "
            "balance circuit model.",
        ],
    }
