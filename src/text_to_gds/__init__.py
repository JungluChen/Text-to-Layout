"""Deprecated import aliases for the former :mod:`text_to_gds` namespace.

All implementation now lives under :mod:`textlayout`.  A lazy import finder
keeps historical deep imports working without duplicating implementation in
this package.  New code must import :mod:`textlayout` directly.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings
from types import ModuleType
from typing import Any

__version__ = "0.3.0"
__textlayout_shim__ = True

_ALIAS_ROOT = "text_to_gds"
_TARGET_ROOT = "textlayout._legacy"
_PHYSICAL_SHIMS = frozenset({"_deprecation", "textlayout_compat"})
_PUBLIC_NAMES = (
    "golden_compare",
    "GeometryIntelligenceEngine",
    "DesignGraphEngine",
    "TopologyReasoningEngine",
    "EngineeringRuleEngine",
    "LiteratureKnowledgeGraph",
    "DESIGN_RULES_FROM_LITERATURE",
    "DesignMemory",
    "EngineeringReasoner",
    "DesignOptimizationEngine",
    "DeviceUnderstandingEngine",
    "EngineeringVisualizationEngine",
    "DigitalTwinEngine",
    "generate_jpa_layout",
    "generate_transmon_layout",
)
__all__ = ["__version__", *_PUBLIC_NAMES]


class _AliasLoader(importlib.abc.Loader):
    """Load one historical module name from its canonical textlayout module."""

    def __init__(self, alias: str, target: str, *, is_package: bool) -> None:
        self.alias = alias
        self.target = target
        self.is_package = is_package

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        target_module = importlib.import_module(self.target)
        spec = module.__spec__
        loader = module.__loader__
        module.__dict__.update(target_module.__dict__)
        module.__dict__.update(
            {
                "__name__": self.alias,
                "__package__": self.alias if self.is_package else self.alias.rpartition(".")[0],
                "__loader__": loader,
                "__spec__": spec,
                "__textlayout_shim__": True,
                "__textlayout_target__": self.target,
            }
        )
        if self.is_package:
            module.__path__ = target_module.__path__  # type: ignore[attr-defined]


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Map ``text_to_gds.x`` to ``textlayout._legacy.x`` on demand."""

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        prefix = _ALIAS_ROOT + "."
        if not fullname.startswith(prefix):
            return None
        suffix = fullname[len(prefix) :]
        if suffix.split(".", 1)[0] in _PHYSICAL_SHIMS:
            return None
        target_name = f"{_TARGET_ROOT}.{suffix}"
        target_spec = importlib.util.find_spec(target_name)
        if target_spec is None:
            return None
        is_package = target_spec.submodule_search_locations is not None
        return importlib.util.spec_from_loader(
            fullname,
            _AliasLoader(fullname, target_name, is_package=is_package),
            is_package=is_package,
        )


if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

warnings.warn(
    "text_to_gds is deprecated; import from textlayout instead.",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str) -> Any:
    if name in _PUBLIC_NAMES:
        return getattr(importlib.import_module(_TARGET_ROOT), name)
    raise AttributeError(name)

