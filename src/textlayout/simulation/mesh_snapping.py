"""MeshSnappingGuard — prevent zero-signal FDTD excitation in openEMS.

Root cause: when CPW port terminals (signal-to-ground) collapse onto identical
or adjacent Yee mesh lines, the excitation injects zero energy.  The entire
FDTD run then produces NaN/zero S-parameters because the denominator (incident
power) is zero.

The guard inspects the mesh lines and port geometry and asserts that every
port gap spans at least ``min_distinct_lines`` distinct Yee grid lines.  If the
constraint is violated it inserts the minimum additional lines needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class PortTerminal:
    """One CPW excitation port between signal and ground edges."""

    port_index: int
    # The two y-coordinates (or x, depending on orientation) that must span
    # distinct Yee lines.
    terminal_low: float
    terminal_high: float
    axis: str = "y"  # which axis the gap lives on


@dataclass(frozen=True)
class SnappingDiagnostic:
    """Result of the mesh-snapping check for one port."""

    port_index: int
    axis: str
    terminal_low: float
    terminal_high: float
    gap_um: float
    distinct_lines_before: int
    distinct_lines_after: int
    lines_inserted: int
    passed: bool
    detail: str


@dataclass
class MeshSnappingResult:
    """Aggregate result from the guard across all ports."""

    passed: bool
    diagnostics: list[SnappingDiagnostic] = field(default_factory=list)
    mesh_lines_before: dict[str, list[float]] = field(default_factory=dict)
    mesh_lines_after: dict[str, list[float]] = field(default_factory=dict)
    min_distinct_lines: int = 3

    @property
    def any_lines_inserted(self) -> bool:
        return any(d.lines_inserted > 0 for d in self.diagnostics)

    def to_dict(self) -> dict[str, object]:
        """JSON-serialisable audit record written next to generated inputs."""
        return {
            "passed": self.passed,
            "min_distinct_lines": self.min_distinct_lines,
            "any_lines_inserted": self.any_lines_inserted,
            "diagnostics": [
                {
                    "port_index": d.port_index,
                    "axis": d.axis,
                    "terminal_low_um": d.terminal_low,
                    "terminal_high_um": d.terminal_high,
                    "gap_um": d.gap_um,
                    "distinct_lines_before": d.distinct_lines_before,
                    "distinct_lines_after": d.distinct_lines_after,
                    "lines_inserted": d.lines_inserted,
                    "passed": d.passed,
                    "detail": d.detail,
                }
                for d in self.diagnostics
            ],
        }


class MeshSnappingGuard:
    """Automated guard ensuring CPW port excitation gaps span at least min_distinct_lines Yee lines."""

    def __init__(self, min_distinct_lines: int = 3) -> None:
        self.min_distinct_lines = min_distinct_lines

    def snap(
        self,
        mesh_lines: dict[str, list[float]],
        ports: list[PortTerminal],
    ) -> MeshSnappingResult:
        return snap_mesh_lines(mesh_lines, ports, min_distinct_lines=self.min_distinct_lines)

    def verify_gap_span(
        self,
        mesh_lines: Sequence[float],
        terminal_low: float,
        terminal_high: float,
    ) -> bool:
        low = min(terminal_low, terminal_high)
        high = max(terminal_low, terminal_high)
        distinct = _count_distinct_in_interval(mesh_lines, low, high)
        return len(set(round(x, 9) for x in distinct)) >= self.min_distinct_lines


def _count_distinct_in_interval(
    lines: Sequence[float], low: float, high: float, *, tol: float = 1e-9
) -> list[float]:
    """Return the mesh lines that fall strictly within [low, high]."""
    return [x for x in lines if low - tol <= x <= high + tol]


def snap_mesh_lines(
    mesh_lines: dict[str, list[float]],
    ports: list[PortTerminal],
    *,
    min_distinct_lines: int = 3,
) -> MeshSnappingResult:
    """Ensure every port gap spans at least ``min_distinct_lines`` Yee lines.

    Mutates ``mesh_lines`` in-place by inserting uniformly spaced lines into the
    port gap when the constraint is not met.

    Returns the snapping result with diagnostics per port.
    """
    if min_distinct_lines < 2:
        raise ValueError("min_distinct_lines must be at least 2")

    mesh_before = {axis: sorted(set(lines)) for axis, lines in mesh_lines.items()}
    diagnostics: list[SnappingDiagnostic] = []
    all_passed = True

    for port in ports:
        axis = port.axis
        if axis not in mesh_lines:
            mesh_lines[axis] = []

        low = min(port.terminal_low, port.terminal_high)
        high = max(port.terminal_low, port.terminal_high)
        gap = high - low
        if gap <= 0:
            diagnostics.append(
                SnappingDiagnostic(
                    port_index=port.port_index,
                    axis=axis,
                    terminal_low=low,
                    terminal_high=high,
                    gap_um=0.0,
                    distinct_lines_before=0,
                    distinct_lines_after=0,
                    lines_inserted=0,
                    passed=False,
                    detail="port gap is zero; terminals overlap — excitation will inject no energy",
                )
            )
            all_passed = False
            continue

        existing = _count_distinct_in_interval(mesh_lines[axis], low, high)
        n_before = len(set(round(x, 12) for x in existing))

        if n_before >= min_distinct_lines:
            diagnostics.append(
                SnappingDiagnostic(
                    port_index=port.port_index,
                    axis=axis,
                    terminal_low=low,
                    terminal_high=high,
                    gap_um=gap,
                    distinct_lines_before=n_before,
                    distinct_lines_after=n_before,
                    lines_inserted=0,
                    passed=True,
                    detail=f"port gap already spans {n_before} ≥ {min_distinct_lines} lines",
                )
            )
            continue

        # Insert uniformly spaced lines to meet the constraint.
        needed = min_distinct_lines - n_before
        # Place lines uniformly across the gap, avoiding the exact endpoints
        # (which are already accounted for as boundary coordinates).
        step = gap / (needed + 1)
        inserted: list[float] = []
        for i in range(1, needed + 1):
            new_line = low + i * step
            # Avoid duplicating an existing line.
            if not any(abs(new_line - ex) < 1e-9 for ex in mesh_lines[axis]):
                inserted.append(round(new_line, 12))

        mesh_lines[axis] = sorted(set(mesh_lines[axis]) | set(inserted))

        after = _count_distinct_in_interval(mesh_lines[axis], low, high)
        n_after = len(set(round(x, 12) for x in after))
        ok = n_after >= min_distinct_lines

        if not ok:
            all_passed = False

        diagnostics.append(
            SnappingDiagnostic(
                port_index=port.port_index,
                axis=axis,
                terminal_low=low,
                terminal_high=high,
                gap_um=gap,
                distinct_lines_before=n_before,
                distinct_lines_after=n_after,
                lines_inserted=len(inserted),
                passed=ok,
                detail=(
                    f"inserted {len(inserted)} line(s); gap now spans {n_after} "
                    f"{'≥' if ok else '<'} {min_distinct_lines} lines"
                ),
            )
        )

    mesh_after = {axis: sorted(set(lines)) for axis, lines in mesh_lines.items()}

    return MeshSnappingResult(
        passed=all_passed,
        diagnostics=diagnostics,
        mesh_lines_before=mesh_before,
        mesh_lines_after=mesh_after,
        min_distinct_lines=min_distinct_lines,
    )


def validate_port_energy(
    *,
    port_energies: dict[int, float],
    s_parameters: dict[str, list[complex]] | None = None,
) -> list[str]:
    """Post-simulation check: every port must have injected non-zero energy.

    Returns a list of failure messages (empty = pass).
    """
    failures: list[str] = []
    for port_idx, energy in port_energies.items():
        if not math.isfinite(energy) or energy <= 0:
            failures.append(
                f"port {port_idx}: injected energy = {energy!r} — "
                "zero/non-finite energy means the excitation mesh is collapsed"
            )

    if s_parameters is not None:
        for name, values in s_parameters.items():
            for i, v in enumerate(values):
                if not math.isfinite(v.real) or not math.isfinite(v.imag):
                    failures.append(
                        f"{name}[{i}] = {v!r} — non-finite S-parameter at frequency index {i}"
                    )
                if v.real == 0.0 and v.imag == 0.0:
                    failures.append(
                        f"{name}[{i}] = 0+0j — zero S-parameter at frequency index {i}; "
                        "likely a collapsed port gap"
                    )
    return failures


__all__ = [
    "MeshSnappingGuard",
    "MeshSnappingResult",
    "PortTerminal",
    "SnappingDiagnostic",
    "snap_mesh_lines",
    "validate_port_energy",
]
