"""GDSII exporter via gdsfactory — the *primary* fabrication artifact.

Architectural note: gdsfactory is imported lazily (inside methods), never at
module load, so the deterministic core and the JSON/SVG paths stay free of the
heavy gdsfactory/klayout import cost. The Geometry IR remains the source of
truth; this adapter merely lowers it into a real ``gdsfactory.Component`` and
writes GDSII. Ports declared on the IR become gdsfactory ports.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textlayout.errors import ExportError
from textlayout.models import Geometry, Technology
from textlayout.ports.exporter import Exporter

if TYPE_CHECKING:  # pragma: no cover
    import gdsfactory as gf

_pdk_activated = False


def _ensure_pdk() -> None:
    """Activate gdsfactory's generic PDK once (required for layer resolution)."""
    global _pdk_activated
    if _pdk_activated:
        return
    import gdsfactory as gf

    gf.gpdk.PDK.activate()
    _pdk_activated = True


class GdsExporter(Exporter):
    """Lowers the Geometry IR to a gdsfactory Component and writes GDSII."""

    format: ClassVar[str] = "gds"
    extension: ClassVar[str] = "gds"
    binary: ClassVar[bool] = True

    def render(self, geometry: Geometry, tech: Technology) -> str:
        raise ExportError("GDS is a binary format; use write() or render_bytes().")

    def build_component(self, geometry: Geometry, tech: Technology) -> gf.Component:
        """Build (and return) the gdsfactory Component for ``geometry``."""
        _ensure_pdk()
        import gdsfactory as gf

        # gdsfactory 9 registers every Component in a process-global layout, so a
        # static name would collide on the second export. A unique suffix keeps
        # the top-cell name unique; downstream EM tools key on geometry, not name.
        unique_name = f"{_safe_name(geometry.name)}_{uuid.uuid4().hex[:8]}"
        component = gf.Component(unique_name)
        for poly in geometry.polygons:
            component.add_polygon(list(poly.points), layer=_layer_tuple(tech, poly.layer))
        for port in geometry.ports:
            try:
                component.add_port(
                    name=port.name,
                    center=port.center,
                    width=port.width,
                    orientation=port.orientation,
                    layer=_layer_tuple(tech, port.layer),
                )
            except Exception as exc:  # pragma: no cover - defensive; ports are non-fatal
                raise ExportError(f"Failed to add port {port.name!r}: {exc}") from exc
        return component

    def write(self, geometry: Geometry, tech: Technology, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        component = self.build_component(geometry, tech)
        component.write_gds(str(out))
        return out

    def render_bytes(self, geometry: Geometry, tech: Technology) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(geometry, tech, Path(tmp) / "out.gds")
            return path.read_bytes()


def canonicalize_gds(path: str | Path, *, cell_name: str) -> Path:
    """Rewrite a GDS in place with a deterministic top-cell name.

    gdsfactory gives each export a unique ``<name>_<uuid8>`` top cell to avoid
    process-global registry collisions, so two regenerations of the *same*
    geometry differ only by that random suffix. For committed benchmark
    artifacts that random suffix is the sole source of GDS byte churn. This
    helper reads the file back through KLayout, renames the single top cell to a
    stable ``cell_name``, and rewrites it. KLayout's writer emits no wall-clock
    timestamp, so repeated runs over identical geometry are byte-for-byte equal.
    """
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(path))
    tops = layout.top_cells()
    if len(tops) == 1:
        tops[0].name = cell_name
    options = kdb.SaveLayoutOptions()
    # GDSII BGNLIB/BGNSTR records carry a wall-clock timestamp (1 s resolution);
    # disabling it is what makes the bytes byte-identical across separate runs.
    options.gds2_write_timestamps = False
    layout.write(str(path), options)
    return Path(path)


def _layer_tuple(tech: Technology, layer_name: str) -> tuple[int, int]:
    if tech.has_layer(layer_name):
        info = tech.layer(layer_name)
        return (info.gds_layer, info.gds_datatype)
    return (0, 0)


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in name)
    return cleaned or "component"
