"""Technology library — provides concrete :class:`Technology` instances.

This is the ``knowledge`` layer: it holds *data* (process stacks), not logic. For
now it ships one built-in generic 2-metal stack. Real PDKs (sky130, an IQM
superconducting process, …) will be added here — or injected from disk — without
touching the engine or generators.
"""

from __future__ import annotations

from pathlib import Path

from textlayout.errors import UnknownTechnologyError
from textlayout.models import LayerInfo, Technology

PDKS_DIR = Path(__file__).resolve().parent / "pdks"

GENERIC_2METAL = Technology(
    name="generic_2metal",
    layers={
        "M1": LayerInfo("M1", gds_layer=1, description="Metal 1", color="#1f77b4"),
        "M2": LayerInfo("M2", gds_layer=2, description="Metal 2", color="#ff7f0e"),
        "JJ": LayerInfo("JJ", gds_layer=3, description="Josephson junction", color="#d62728"),
        "GND": LayerInfo("GND", gds_layer=10, description="Ground plane", color="#7f7f7f"),
        "TEXT": LayerInfo("TEXT", gds_layer=63, description="Labels", color="#2ca02c"),
    },
    grid_nm=5.0,
    default_min_spacing_um=2.0,
    min_spacing_um={"M1": 2.0, "M2": 2.0, "JJ": 0.2, "GND": 2.0},
    default_min_width_um=1.0,
    min_width_um={"M1": 2.0, "M2": 2.0, "JJ": 0.1, "GND": 2.0},
    substrate_epsilon_r=11.9,  # high-resistivity silicon
)


class TechnologyLibrary:
    """A small, injectable registry of technologies.

    Holds no global mutable state — callers construct an instance (or use
    :func:`default_technology_library`) and pass it in via dependency injection.
    """

    def __init__(self, technologies: list[Technology] | None = None) -> None:
        self._by_name: dict[str, Technology] = {}
        for tech in technologies or []:
            self.register(tech)

    def register(self, technology: Technology) -> None:
        self._by_name[technology.name] = technology

    def get(self, name: str) -> Technology:
        try:
            return self._by_name[name]
        except KeyError:
            raise UnknownTechnologyError(name, list(self._by_name)) from None

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def __contains__(self, name: object) -> bool:
        return name in self._by_name


def default_technology_library() -> TechnologyLibrary:
    """Construct a library pre-loaded with the built-in technologies.

    ``generic_2metal`` stays the hardcoded :class:`Technology` above for zero
    behavior change on existing examples. Any PDK YAML under
    ``src/textlayout/knowledge/pdks/`` is additionally loaded and registered
    under its own PDK name (e.g. ``example_superconducting_pdk``), so new
    designs can select a richer illustrative process via
    ``LayoutSpec.technology`` with no CLI/API changes. A PDK that fails to
    load is skipped, not fatal — the built-in technology must always be
    available.
    """
    library = TechnologyLibrary([GENERIC_2METAL])
    if PDKS_DIR.is_dir():
        from textlayout.pdk import load_pdk, pdk_to_technology

        for pdk_path in sorted(PDKS_DIR.glob("*.yaml")):
            try:
                pdk = load_pdk(pdk_path)
            except Exception:  # noqa: BLE001 - a malformed example must not break startup
                continue
            if pdk.name in library:
                continue  # generic_2metal (and any future hardcoded name) wins
            library.register(pdk_to_technology(pdk))
    return library
