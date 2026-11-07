"""Runtime availability probes for the 100-target integration catalog.

:mod:`textlayout.integrations.catalog` is a pure data inventory. This module
adds the *probe* side used by ``textlayout doctor``: for every catalog target
it declares how presence can be detected deterministically (an importable
Python module, an executable on ``PATH``/``.tools``/``$HOME/.cache/textlayout-*``,
or both) and reports one of three statuses:

``FOUND``
    A module spec or executable was located (and, when ``import_modules`` is
    requested, the module imported without raising).
``MISSING``
    Nothing was located. Downstream adapters emit ``SKIPPED_SOLVER_ABSENT``.
``BROKEN``
    Something was located but failed its probe (import raised, or the
    executable path is not a regular file).

Targets with no deterministic probe (research code bases, commercial bridges
that need a licence) are reported as ``NOT_PROBED`` rather than guessed.
Probing never installs, downloads, or executes solver workloads.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from textlayout._paths import repository_root
from textlayout.integrations.catalog import IntegrationTarget, load_targets

FOUND = "FOUND"
MISSING = "MISSING"
BROKEN = "BROKEN"
NOT_PROBED = "NOT_PROBED"

INVENTORY_SCHEMA = "textlayout.integration-inventory.v1"

ProbeKind = Literal["python", "executable", "python+executable", "none"]


@dataclass(frozen=True, slots=True)
class ToolProbeSpec:
    """How one catalog target can be detected without executing it."""

    target_id: int
    modules: tuple[str, ...] = ()
    executables: tuple[str, ...] = ()
    env_var: str | None = None
    note: str | None = None

    @property
    def kind(self) -> ProbeKind:
        if self.modules and self.executables:
            return "python+executable"
        if self.modules:
            return "python"
        if self.executables:
            return "executable"
        return "none"


@dataclass(slots=True)
class ToolProbe:
    """Result of probing one catalog target."""

    target_id: int
    pillar: int
    name: str
    status: str
    kind: ProbeKind
    detail: str = ""
    path: str | None = None
    version: str | None = None
    modules: tuple[str, ...] = ()
    executables: tuple[str, ...] = ()
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.target_id,
            "pillar": self.pillar,
            "name": self.name,
            "status": self.status,
            "probe_kind": self.kind,
            "detail": self.detail,
            "path": self.path,
            "version": self.version,
            "modules": list(self.modules),
            "executables": list(self.executables),
            **self.extras,
        }


def _spec(
    target_id: int,
    *,
    modules: Iterable[str] = (),
    executables: Iterable[str] = (),
    env_var: str | None = None,
    note: str | None = None,
) -> ToolProbeSpec:
    return ToolProbeSpec(
        target_id=target_id,
        modules=tuple(modules),
        executables=tuple(executables),
        env_var=env_var,
        note=note,
    )


#: Deterministic probe definitions keyed by catalog id. Keep ids aligned with
#: ``targets.json``; :func:`load_probe_specs` validates the mapping.
PROBE_SPECS: tuple[ToolProbeSpec, ...] = (
    # Pillar 1 -- quantum chip layout & micro-primitives
    _spec(1, modules=("kqcircuits",)),
    _spec(2, modules=("qiskit_metal",)),
    _spec(3, modules=("pyEPR",)),
    _spec(4, modules=("circuitq",)),
    _spec(5, modules=("scqubits",)),
    _spec(6, modules=("SQcircuit",)),
    _spec(7, modules=("squadds",)),
    _spec(8, modules=("qeda",)),
    _spec(9, modules=("pycqed",)),
    _spec(10, modules=("qiskit_dynamics",)),
    # Pillar 2 -- 2.5D/3D EM & multiphysics
    _spec(11, executables=("palace", "palace.exe"), env_var="TEXTLAYOUT_PALACE"),
    _spec(12, executables=("openEMS", "openEMS.exe"), env_var="TEXTLAYOUT_OPENEMS"),
    _spec(13, executables=("FasterCap", "fastercap", "FastCap"), env_var="TEXTLAYOUT_FASTERCAP"),
    _spec(14, executables=("fasthenry", "FastHenry2"), env_var="TEXTLAYOUT_FASTHENRY"),
    _spec(15, modules=("meep",), executables=("meep",)),
    _spec(16, modules=("gprMax",), executables=("gprmax",)),
    _spec(17, executables=("ElmerSolver", "ElmerGrid"), env_var="TEXTLAYOUT_ELMER"),
    _spec(18, modules=("mfem",), executables=("mfem",)),
    _spec(19, executables=("scuff-scatter", "scuff-cas3D"), env_var="TEXTLAYOUT_SCUFF"),
    _spec(20, modules=("dolfinx", "dolfin")),
    # Pillar 3 -- RF network analysis
    _spec(21, modules=("skrf",)),
    _spec(22, executables=("qucs-s", "qucsator"), env_var="TEXTLAYOUT_QUCS"),
    _spec(23, executables=("txline",)),
    _spec(24, modules=("rfplot",)),
    _spec(25, note="Research workflow; no PyPI distribution or executable to probe."),
    _spec(26, modules=("coupledlines",)),
    _spec(27, note="Clone/research artefact; no deterministic install surface."),
    _spec(28, modules=("smithpredictor",)),
    _spec(29, modules=("pysmith",)),
    _spec(30, executables=("atlc",), env_var="TEXTLAYOUT_ATLC"),
    # Pillar 4 -- layout compilation & meshing
    _spec(31, modules=("gdsfactory",)),
    _spec(32, modules=("kfactory",)),
    _spec(33, modules=("klayout.db",), executables=("klayout", "klayout_app")),
    _spec(34, modules=("phidl",)),
    _spec(35, modules=("gdspy",)),
    _spec(36, modules=("shapely",)),
    _spec(37, modules=("pyclipper", "clipper2")),
    _spec(38, modules=("trimesh",)),
    _spec(39, modules=("gmsh",), executables=("gmsh", "gmsh.exe"), env_var="TEXTLAYOUT_GMSH"),
    _spec(40, modules=("OCC", "cadquery")),
    # Pillar 5 -- superconducting / RSFQ SPICE
    _spec(41, executables=("josim-cli", "josim"), env_var="TEXTLAYOUT_JOSIM"),
    _spec(42, executables=("pscan2", "pscan"), env_var="TEXTLAYOUT_PSCAN2"),
    _spec(43, executables=("wrspice", "wrspice.exe"), env_var="TEXTLAYOUT_WRSPICE"),
    _spec(44, executables=("xic", "wrspice")),
    _spec(45, note="SuperCAD is a desktop suite without a headless probe surface."),
    _spec(46, executables=("jsim", "jsim_n")),
    _spec(47, executables=("spicej",)),
    _spec(48, modules=("sfqex",)),
    _spec(49, executables=("coldspice",)),
    _spec(50, note="PDK data, not a tool; validated by textlayout.pdk when present."),
    # Pillar 6 -- analog / mixed-signal SPICE
    _spec(51, executables=("ngspice", "ngspice.exe"), env_var="TEXTLAYOUT_NGSPICE"),
    _spec(52, executables=("Xyce", "xyce"), env_var="TEXTLAYOUT_XYCE"),
    _spec(53, modules=("PySpice",)),
    _spec(54, executables=("openvaf",)),
    _spec(55, executables=("xschem",)),
    _spec(56, executables=("spiceopus",)),
    _spec(57, modules=("ahkab",)),
    _spec(58, modules=("pycircuit",)),
    _spec(59, executables=("qucs", "qucsator")),
    _spec(60, executables=("gnucap",)),
    # Pillar 7 -- physical design & signoff
    _spec(61, executables=("openroad",), env_var="TEXTLAYOUT_OPENROAD"),
    _spec(62, executables=("flow.tcl", "openlane")),
    _spec(63, executables=("magic",), env_var="TEXTLAYOUT_MAGIC"),
    _spec(64, executables=("netgen",), env_var="TEXTLAYOUT_NETGEN"),
    _spec(65, modules=("align",)),
    _spec(66, modules=("siliconcompiler",), executables=("sc",)),
    _spec(67, modules=("bag",)),
    _spec(68, modules=("gds2parasitics",)),
    _spec(69, modules=("openfasoc",)),
    _spec(70, note="Research layout tool without a published install surface."),
    # Pillar 8 -- AI placement & routing (research code bases)
    _spec(71, modules=("circuit_training",)),
    _spec(72, modules=("dreamplace",)),
    _spec(73, modules=("autockt",)),
    _spec(74, note="Research code base; no deterministic install surface."),
    _spec(75, modules=("glayout",)),
    _spec(76, note="Benchmark data set, not an installable tool."),
    _spec(77, note="Research model; no deterministic install surface."),
    _spec(78, note="Research model; no deterministic install surface."),
    _spec(79, note="Research model; no deterministic install surface."),
    _spec(80, note="Research model; no deterministic install surface."),
    # Pillar 9 -- commercial bridges (licence required; presence only)
    _spec(81, modules=("pyaedt", "ansys.aedt.core")),
    _spec(82, note="CST Python bridge ships with a licensed CST install; not probed."),
    _spec(83, note="Keysight ADS Python bridge ships with a licensed ADS install; not probed."),
    _spec(84, note="Cadence SKILL bridge requires a licensed Virtuoso install; not probed."),
    _spec(85, modules=("klayout",)),
    _spec(86, note="SonnetLab requires a licensed Sonnet install; not probed."),
    _spec(87, modules=("pdkmaster",)),
    _spec(88, note="GDS2Touchstone has no public install surface; not probed."),
    _spec(89, note="Virtuoso bridge requires a licensed Cadence install; not probed."),
    _spec(90, note="Calibre interface requires a licensed Siemens install; not probed."),
    # Pillar 10 -- visualisation & diagnostics
    _spec(91, modules=("pyvista",)),
    _spec(92, modules=("meshio",)),
    _spec(93, modules=("mayavi",)),
    _spec(94, note="Browser viewer bundled under web/; no runtime probe."),
    _spec(95, modules=("plotly",)),
    _spec(96, modules=("rich",)),
    _spec(97, modules=("langgraph",)),
    _spec(98, modules=("h5py",)),
    _spec(99, modules=("zarr",)),
    _spec(100, modules=("netron",)),
)


def load_probe_specs() -> dict[int, ToolProbeSpec]:
    """Return probe specs keyed by catalog id, validated against the catalog."""
    specs = {spec.target_id: spec for spec in PROBE_SPECS}
    if len(specs) != len(PROBE_SPECS):
        raise ValueError("duplicate probe spec ids")
    catalog_ids = {target.id for target in load_targets()}
    if set(specs) != catalog_ids:
        missing = sorted(catalog_ids - set(specs))
        extra = sorted(set(specs) - catalog_ids)
        raise ValueError(f"probe specs out of sync with catalog: missing={missing} extra={extra}")
    return specs


def tool_cache_roots(home: Path | None = None) -> list[Path]:
    """Directories where compiled tools may live outside the Python tree.

    Order: ``$TEXTLAYOUT_TOOLS_DIR`` or ``<repo>/.tools``, then every
    ``$HOME/.cache/textlayout-*`` directory (sorted for determinism).
    """
    roots: list[Path] = []
    override = os.environ.get("TEXTLAYOUT_TOOLS_DIR")
    roots.append(Path(override) if override else repository_root() / ".tools")
    cache_home = Path(os.environ.get("XDG_CACHE_HOME") or (home or Path.home()) / ".cache")
    try:
        roots.extend(sorted(p for p in cache_home.glob("textlayout-*") if p.is_dir()))
    except OSError:
        pass
    return roots


def _locate_executable(
    names: tuple[str, ...], env_var: str | None, roots: list[Path]
) -> tuple[str | None, str | None]:
    """Return ``(path, problem)``; ``problem`` is set when a located path is unusable."""
    if env_var:
        explicit = os.environ.get(env_var)
        if explicit:
            candidate = Path(explicit).expanduser()
            if candidate.is_file():
                return str(candidate), None
            resolved = shutil.which(explicit)
            if resolved:
                return resolved, None
            return None, f"{env_var}={explicit!r} does not resolve to an executable"
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved, None
    for root in roots:
        if not root.is_dir():
            continue
        for name in names:
            patterns = (name, f"*/{name}", f"*/bin/{name}", f"*/*/{name}")
            for pattern in patterns:
                for candidate in sorted(root.glob(pattern)):
                    try:
                        if candidate.is_file() and os.access(candidate, os.X_OK):
                            return str(candidate), None
                    except OSError:
                        continue
    return None, None


def _module_version(name: str) -> str | None:
    try:
        module = importlib.import_module(name.split(".", 1)[0])
    except Exception:  # noqa: BLE001 - version is advisory only
        return None
    version = getattr(module, "__version__", None)
    return str(version) if version is not None else None


def _probe_modules(modules: tuple[str, ...], *, import_modules: bool) -> ToolProbe | None:
    """Return a partial probe for the first locatable module, or ``None``."""
    for name in modules:
        try:
            spec = importlib.util.find_spec(name)
        except ModuleNotFoundError:
            # Dotted name whose parent package is absent: plainly not installed.
            continue
        except (ImportError, ValueError, AttributeError) as exc:
            return ToolProbe(0, 0, "", BROKEN, "python", f"find_spec({name!r}) raised {exc}")
        if spec is None:
            continue
        origin = spec.origin if spec.origin not in (None, "namespace") else None
        if not import_modules:
            return ToolProbe(0, 0, "", FOUND, "python", f"module {name} located", origin)
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - report import failure honestly
            return ToolProbe(
                0, 0, "", BROKEN, "python", f"import {name}: {type(exc).__name__}: {exc}", origin
            )
        return ToolProbe(
            0, 0, "", FOUND, "python", f"module {name} imported", origin, _module_version(name)
        )
    return None


def probe_target(
    target: IntegrationTarget,
    spec: ToolProbeSpec,
    *,
    import_modules: bool = False,
    roots: list[Path] | None = None,
) -> ToolProbe:
    """Probe one target. Never raises; failures are reported as ``BROKEN``."""
    roots = tool_cache_roots() if roots is None else roots
    base = ToolProbe(
        target_id=target.id,
        pillar=target.pillar,
        name=target.name,
        status=NOT_PROBED,
        kind=spec.kind,
        detail=spec.note or "no deterministic probe defined",
        modules=spec.modules,
        executables=spec.executables,
    )
    if spec.kind == "none":
        return base

    module_result = (
        _probe_modules(spec.modules, import_modules=import_modules) if spec.modules else None
    )
    if module_result is not None:
        base.status = module_result.status
        base.detail = module_result.detail
        base.path = module_result.path
        base.version = module_result.version
        if base.status == FOUND or not spec.executables:
            return base

    if spec.executables:
        path, problem = _locate_executable(spec.executables, spec.env_var, roots)
        if path is not None:
            base.status = FOUND
            base.detail = f"executable {path}"
            base.path = path
            return base
        if problem:
            base.status = BROKEN
            base.detail = problem
            return base

    if base.status == NOT_PROBED:
        base.status = MISSING
        base.detail = "not located on PATH, .tools, or $HOME/.cache/textlayout-*"
        if spec.modules:
            base.detail = f"module(s) {', '.join(spec.modules)} not importable; " + base.detail
    return base


def probe_inventory(
    *, import_modules: bool = False, roots: list[Path] | None = None
) -> list[ToolProbe]:
    """Probe every catalog target in id order."""
    specs = load_probe_specs()
    roots = tool_cache_roots() if roots is None else roots
    return [
        probe_target(target, specs[target.id], import_modules=import_modules, roots=roots)
        for target in load_targets()
    ]


def summarize_inventory(probes: Iterable[ToolProbe]) -> dict[str, Any]:
    """Aggregate counts per status and per pillar for reports."""
    items = list(probes)
    by_status: dict[str, int] = {FOUND: 0, MISSING: 0, BROKEN: 0, NOT_PROBED: 0}
    by_pillar: dict[int, dict[str, int]] = {}
    for probe in items:
        by_status[probe.status] = by_status.get(probe.status, 0) + 1
        pillar = by_pillar.setdefault(probe.pillar, dict.fromkeys(by_status, 0))
        pillar[probe.status] = pillar.get(probe.status, 0) + 1
    return {
        "schema": INVENTORY_SCHEMA,
        "total": len(items),
        "by_status": by_status,
        "by_pillar": {str(k): v for k, v in sorted(by_pillar.items())},
        "found": [probe.name for probe in items if probe.status == FOUND],
        "broken": [probe.name for probe in items if probe.status == BROKEN],
    }


__all__ = [
    "BROKEN",
    "FOUND",
    "INVENTORY_SCHEMA",
    "MISSING",
    "NOT_PROBED",
    "PROBE_SPECS",
    "ToolProbe",
    "ToolProbeSpec",
    "load_probe_specs",
    "probe_inventory",
    "probe_target",
    "summarize_inventory",
    "tool_cache_roots",
]
