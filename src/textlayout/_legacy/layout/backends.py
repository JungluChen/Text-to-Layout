"""LayoutBackend abstraction — Part 3 of TopTask.md.

The LLM chooses a backend and component type.
The backend generates the layout.
The LLM may tune parameters but cannot invent invalid layers or geometry.
If no backend supports the requested device, return "unsupported", not fake layout.

Priority order (per TopTask.md):
  1. KQCircuits  — superconducting quantum layout
  2. Qiskit Metal — superconducting qubit / microwave design
  3. gdsfactory  — generic GDS composition
  4. local_pcells — registered local PCell fallback

Each backend must implement:
  name:              str
  supported_devices: list[str]
  generate(intent, gds_path, metadata_path) -> dict
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from importlib.util import find_spec
import json
from pathlib import Path
from typing import Any


class LayoutBackendError(Exception):
    """Raised when no backend can handle the requested components."""


class LayoutBackend(ABC):
    """Abstract base for all layout backends."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supported_devices(self) -> list[str]: ...

    def can_handle(self, components: list[str]) -> bool:
        supported = set(self.supported_devices)
        return all(c in supported for c in components)

    def available(self) -> bool:
        return True

    @abstractmethod
    def generate(
        self,
        intent: dict[str, Any],
        gds_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any]:
        """Generate GDS and metadata for the given design intent.

        Must return a dict with at least:
            gds_path      Path to generated GDS file
            metadata_path Path to generated metadata JSON
            backend       Backend name
        Never silently invent missing geometry.  Raise on unsupported input.
        """


# ---------------------------------------------------------------------------
# KQCircuits backend (priority 1)
# ---------------------------------------------------------------------------

class KQCircuitsBackend(LayoutBackend):
    """Superconducting quantum layout via KQCircuits."""

    @property
    def name(self) -> str:
        return "kqcircuits"

    @property
    def supported_devices(self) -> list[str]:
        return [
            "cpw",
            "cpw_feedline",
            "cpw_quarter_wave",
            "cpw_quarter_wave_resonator",
            "cpw_resonator",
            "cpw_straight",
            "cpw_taper",
            "ground_plane",
            "junction",
            "manhattan_jj",
            "meander",
            "qubit",
            "resonator",
            "transmon",
            "waveguide",
        ]

    def available(self) -> bool:
        return find_spec("kqcircuits") is not None

    def generate(
        self,
        intent: dict[str, Any],
        gds_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any]:
        from textlayout._legacy.backends.kqcircuits_backend import KQCircuitsBackend as OrchestrationBackend

        request = _intent_to_backend_request(intent)
        result = OrchestrationBackend().generate(request, output_dir=gds_path.parent)
        metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        raise LayoutBackendError(result["reason"])


# ---------------------------------------------------------------------------
# Qiskit Metal backend (priority 2)
# ---------------------------------------------------------------------------

class QiskitMetalBackend(LayoutBackend):
    """Superconducting qubit and microwave design via Qiskit Metal."""

    @property
    def name(self) -> str:
        return "qiskit_metal"

    @property
    def supported_devices(self) -> list[str]:
        return [
            "transmon",
            "transmon_pocket",
            "transmon_cross",
            "resonator",
            "coupler",
            "cpw",
            "cpw_route",
            "cpw_feedline",
            "launch_pad",
            "launchpad",
            "open_to_ground",
            "short_to_ground",
            "flux_line",
        ]

    def available(self) -> bool:
        return find_spec("qiskit_metal") is not None

    def generate(
        self,
        intent: dict[str, Any],
        gds_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any]:
        from textlayout._legacy.backends.qiskit_metal_backend import QiskitMetalBackend as OrchestrationBackend

        request = _intent_to_backend_request(intent)
        result = OrchestrationBackend().generate(request, output_dir=gds_path.parent)
        metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        raise LayoutBackendError(result["reason"])


# ---------------------------------------------------------------------------
# gdsfactory backend (priority 3)
# ---------------------------------------------------------------------------

class GDSFactoryBackend(LayoutBackend):
    """Generic GDS composition via gdsfactory."""

    @property
    def name(self) -> str:
        return "gdsfactory"

    @property
    def supported_devices(self) -> list[str]:
        return [
            "straight",
            "bend_euler",
            "cross",
            "rectangle",
            "circle",
            "polygon",
            "pack",
            "cpw_feedline",
        ]

    def generate(
        self,
        intent: dict[str, Any],
        gds_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any]:
        from textlayout._legacy.backends.gdsfactory_backend import GDSFactoryBackend as OrchestrationBackend

        request = _intent_to_backend_request(intent)
        result = OrchestrationBackend().generate(request, output_dir=gds_path.parent)
        metadata_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if result["status"] != "EXECUTED":
            raise LayoutBackendError(result["reason"])
        artifacts = result.get("artifacts", {})
        return {
            "gds_path": Path(artifacts.get("gds", gds_path)),
            "metadata_path": metadata_path,
            "backend": self.name,
        }


# ---------------------------------------------------------------------------
# Local PCells backend (priority 4 — fallback)
# ---------------------------------------------------------------------------

_LOCAL_PCELL_MAP = {
    "manhattan_josephson_junction": "manhattan_josephson_junction",
    "manhattan_jj":                 "manhattan_josephson_junction",
    "jj_ic_calibration_array":      "jj_ic_calibration_array",
    "cpw_quarter_wave_resonator":   "cpw_quarter_wave_resonator",
    "cpw_feedline":                 "cpw_quarter_wave_resonator",
    "lumped_jpa_seed":              "lumped_jpa_seed",
    "meander_inductor":             "meander_inductor",
    "flux_bias_line":               "flux_bias_line",
    "via_stack":                    "via_stack",
    "via_chain_monitor":            "via_chain_monitor",
    "idc_capacitor":                "lumped_jpa_seed",
    "flux_line":                    "flux_bias_line",
    "port":                         None,  # meta-directive, not a PCell
}


class LocalPCellsBackend(LayoutBackend):
    """Registered local PCell fallback."""

    @property
    def name(self) -> str:
        return "local_pcells"

    @property
    def supported_devices(self) -> list[str]:
        return [k for k, v in _LOCAL_PCELL_MAP.items() if v is not None]

    def generate(
        self,
        intent: dict[str, Any],
        gds_path: Path,
        metadata_path: Path,
    ) -> dict[str, Any]:
        from textlayout._legacy.server import compile_layout

        directives = intent.get("directives", [])
        components = [d["component"] for d in directives if d["component"] != "port"]
        if not components:
            raise LayoutBackendError("No non-port components in directives")

        primary = components[0]
        pcell_name = _LOCAL_PCELL_MAP.get(primary)
        if pcell_name is None:
            raise LayoutBackendError(
                f"Local PCell not found for component '{primary}'. "
                "No backend supports this device — returning unsupported."
            )

        params: dict[str, Any] = {}
        for d in directives:
            params.update(d.get("params", {}))

        result = compile_layout(
            pcell=pcell_name,
            parameters=params,
            output_name=gds_path.name,
        )
        gen_gds = Path(result["gds_path"])
        metadata: dict[str, Any] = {
            "backend": self.name,
            "device": intent.get("device"),
            "technology": intent.get("technology"),
            "pcell": pcell_name,
            "params": params,
            "sidecar_path": result.get("sidecar_path"),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {
            "gds_path": gen_gds,
            "metadata_path": metadata_path,
            "backend": self.name,
            "sidecar_path": result.get("sidecar_path"),
        }


# ---------------------------------------------------------------------------
# Backend registry and selector
# ---------------------------------------------------------------------------

_PRIORITY_BACKENDS: list[type[LayoutBackend]] = [
    KQCircuitsBackend,
    QiskitMetalBackend,
    GDSFactoryBackend,
    LocalPCellsBackend,
]


def select_backend(
    technology: str,
    components: list[str],
    force: str | None = None,
) -> LayoutBackend:
    """Return the highest-priority backend that supports all requested components.

    Parameters
    ----------
    technology:
        Technology ID from the SuperCAD TECH directive.
    components:
        List of ADD directive component names.
    force:
        If given, only that backend is tried.

    Raises
    ------
    LayoutBackendError
        When no backend supports the requested components.
    """
    # Remove meta-directives that aren't real PCells
    real_components = [c for c in components if c != "port"]

    backends = _PRIORITY_BACKENDS
    if force is not None:
        backends = [b for b in backends if b().name == force]
        if not backends:
            raise LayoutBackendError(f"Unknown backend name: {force!r}")

    for backend_cls in backends:
        backend = backend_cls()
        if force is None and not backend.available():
            continue
        if backend.can_handle(real_components):
            return backend

    raise LayoutBackendError(
        f"No backend supports all requested components {real_components!r} "
        f"for technology '{technology}'. "
        "Returning unsupported — no fake layout will be generated."
    )


def _intent_to_backend_request(intent: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    components: list[str] = []
    for directive in intent.get("directives", []):
        component = directive.get("component")
        if component:
            components.append(component)
        params.update(directive.get("params", {}))
    return {
        "device": intent.get("device"),
        "technology": intent.get("technology"),
        "components": components,
        "parameters": params,
    }
