"""Deprecation-shim helpers for the frozen ``text_to_gds`` legacy package.

The supported implementation namespace is ``textlayout`` (see
``docs/ARCHITECTURE.md`` and ``scripts/check_namespace_boundary.py``). As legacy
capabilities are ported, the old ``text_to_gds`` module becomes a *thin
re-export shim*: it imports the real implementation from ``textlayout``, warns
once that the legacy path is deprecated, and re-exports the public names so
existing callers keep working unchanged.

:func:`deprecated_reexport` is the single tool for that. A module that calls it
is recognised as a shim by the namespace-boundary guard (it sets the
``__textlayout_shim__`` marker), so it is exempt from the legacy freeze: new
*implementation* files are rejected, new *shims* are allowed.

This module is enforcement infrastructure, not a legacy feature, so the guard
allows it under ``INFRASTRUCTURE_ALLOW``.
"""

from __future__ import annotations

import importlib
import warnings
from collections.abc import Sequence
from typing import Any

#: Module-level attribute a shim sets so the boundary guard can recognise it
#: structurally (via AST, without importing).
SHIM_MARKER = "__textlayout_shim__"


def deprecated_reexport(
    module_globals: dict[str, Any],
    target: str,
    *,
    names: Sequence[str] | None = None,
    since: str,
    replacement: str | None = None,
    removal: str | None = None,
) -> list[str]:
    """Turn the calling ``text_to_gds`` module into a shim over a ``textlayout`` target.

    Copies the selected public names out of ``target`` into ``module_globals``,
    marks the module as a shim, and emits a single :class:`DeprecationWarning`
    steering callers to the supported namespace.

    Parameters
    ----------
    module_globals:
        The shim module's ``globals()``.
    target:
        Importable ``textlayout`` module to re-export from, e.g. ``"textlayout"``
        or ``"textlayout.evidence"``.
    names:
        Public names to re-export. Defaults to the target's ``__all__`` if it
        defines one, else every non-underscore attribute.
    since:
        Version in which this path became deprecated (for the message).
    replacement:
        Import path callers should move to. Defaults to ``target``.
    removal:
        Version in which the shim will be removed, if known.

    Returns
    -------
    list[str]
        The re-exported names, suitable for assigning to the shim's ``__all__``.
    """
    if not target.split(".")[0] == "textlayout":
        raise ValueError(f"deprecated_reexport target must live under textlayout, got {target!r}")

    module = importlib.import_module(target)
    if names is None:
        exported = getattr(module, "__all__", None)
        names = list(exported) if exported is not None else [
            n for n in vars(module) if not n.startswith("_")
        ]

    missing = [n for n in names if not hasattr(module, n)]
    if missing:
        raise AttributeError(f"{target} does not export: {', '.join(sorted(missing))}")

    for name in names:
        module_globals[name] = getattr(module, name)

    module_globals[SHIM_MARKER] = True
    module_globals["__all__"] = list(names)

    shim_name = module_globals.get("__name__", "<shim>")
    replacement = replacement or target
    tail = f" and will be removed in {removal}" if removal else ""
    warnings.warn(
        f"{shim_name} is a deprecated compatibility shim (since {since}{tail}); "
        f"import from {replacement} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return list(names)
