"""Build canonical evidence by re-deriving it from committed solver outputs.

Nothing here trusts a status string. For each showcase the recorded solver
output is re-parsed with the current parser, the value is recomputed, the
convergence criterion the solver actually enforced is read back, and the status
is *computed*:

    parser rejects the output        -> SIMULATION_INVALID
    no convergence criterion         -> SIMULATION_EXECUTED  (never verified)
    converged and inside tolerance   -> PHYSICS_VERIFIED
    converged and outside tolerance  -> SIMULATION_EXECUTED

No solver is re-run. A solver that is unavailable is never invoked and its
evidence is never fabricated.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textlayout.evidence.canonical import (
    CanonicalEvidence,
    ConvergenceMetrics,
    SupersededClaim,
    compute_evidence_id,
    sha256_file,
    sha256_json,
)
from textlayout.evidence.contract import EvidenceStatus

PARSER_VERSION = "2"


@dataclass(frozen=True)
class Recipe:
    """How to re-derive one showcase's headline claim from its own outputs."""

    component: str
    analysis_scope: str
    target_quantity: str
    target_value: float | None
    target_unit: str | None
    #: Solver-level result file that carries command/runtime/return_code.
    result_json: str | None = None
    output_files: tuple[str, ...] = ()
    input_files: tuple[str, ...] = ()
    parser: str | None = None
    extraction_config: dict[str, Any] = field(default_factory=dict)
    #: Recompute the extracted value from the committed output. Raises when the
    #: output cannot honestly yield a number.
    extract: Callable[[Path], float] | None = None
    #: Read back the convergence criterion the solver actually enforced.
    convergence: Callable[[Path], ConvergenceMetrics] | None = None
    analytical_only: bool = False
    analytical_model: str | None = None
    superseded: SupersededClaim | None = None
    notes: tuple[str, ...] = ()


# --- extractors ------------------------------------------------------------


def _fastercap_mutual_pf(showcase: Path) -> float:
    from textlayout.simulation.fastercap import _parse_capacitance_matrix_pf

    text = (showcase / "extraction/capacitance_input/solver.stdout.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    matrix = _parse_capacitance_matrix_pf(text)
    if len(matrix) < 2:
        raise ValueError("FasterCap matrix has no mutual term")
    return abs(matrix[0][1])


def _fasthenry_inductance_nh(showcase: Path) -> float:
    from textlayout.simulation.runners import parse_fasthenry_inductance

    text = (showcase / "extraction/capacitance_input/Zc.mat").read_text(encoding="utf-8")
    return parse_fasthenry_inductance(text) * 1e9


def _cpw_impedance_ohm(showcase: Path) -> float:
    from textlayout.simulation.runners import extract_cpw_from_touchstone

    path = showcase / "extraction/capacitance_input/openems_result.s2p"
    return float(extract_cpw_from_touchstone(path, frequency_ghz=6.0)["characteristic_impedance_ohm"])


def _resonance_ghz(showcase: Path) -> float:
    from textlayout.simulation.runners import extract_resonance_metrics_from_touchstone

    path = showcase / "extraction/capacitance_input/openems_result.s2p"
    return float(extract_resonance_metrics_from_touchstone(path)["resonance_frequency_ghz"])


# --- convergence read-back --------------------------------------------------


def _fastercap_convergence(showcase: Path) -> ConvergenceMetrics:
    """FasterCap's `-a<tol>` is automatic refinement to a relative tolerance."""
    import json as _json

    result = _json.loads(
        (showcase / "extraction/capacitance_result.json").read_text(encoding="utf-8")
    )
    tolerance = None
    for token in result.get("command", []):
        if isinstance(token, str) and token.startswith("-a"):
            tolerance = float(token[2:]) * 100.0
    if tolerance is None:
        return ConvergenceMetrics(
            method="none_recorded",
            refinement_levels=1,
            converged=False,
            notes=["no -a refinement tolerance in the recorded command"],
        )
    return ConvergenceMetrics(
        method="fastercap_automatic_refinement",
        refinement_levels=1,
        threshold_percent=tolerance,
        converged=result.get("return_code") == 0,
        notes=[
            f"solver refined its panel discretisation until the relative change "
            f"fell below {tolerance:g}% (-a flag), and exited 0"
        ],
    )


def _openems_convergence(showcase: Path) -> ConvergenceMetrics:
    """FDTD convergence: the field energy decayed and the source pulse finished.

    This is a genuine time-domain convergence criterion -- a DFT taken before
    the ring-down completes is wrong. It is NOT a mesh-refinement study, and
    that gap is stated rather than glossed.
    """
    from textlayout.simulation.runners import _openems_convergence_problem

    stdout = showcase / "extraction/capacitance_input/solver.stdout.txt"
    problem = _openems_convergence_problem(stdout)
    return ConvergenceMetrics(
        method="fdtd_energy_decay_and_excitation_support",
        refinement_levels=1,
        converged=problem is None,
        notes=(
            ["no mesh-refinement study was performed; only time-domain convergence is evidenced"]
            if problem is None
            else [problem]
        ),
    )


def _no_convergence(_: Path) -> ConvergenceMetrics:
    return ConvergenceMetrics(
        method="none_recorded",
        refinement_levels=1,
        converged=False,
        notes=[
            "FastHenry ran once at the deck's default single-filament "
            "discretisation: the deck declares no nhinc/nwinc, and no refinement "
            "sweep exists. Current crowding in a spiral is unresolved, so no "
            "convergence is evidenced."
        ],
    )


# --- the recipes ------------------------------------------------------------

_IDC_OUTPUTS = ("extraction/capacitance_input/solver.stdout.txt",)
_IDC_INPUTS = ("extraction/capacitance_input/idc.lst", "extraction/capacitance_input/idc.qui")

RECIPES: dict[str, Recipe] = {
    "01_idc_0p6pf": Recipe(
        component="IDC",
        analysis_scope="idc_electrodes",
        target_quantity="capacitance",
        target_value=0.6,
        target_unit="pF",
        result_json="extraction/capacitance_result.json",
        output_files=_IDC_OUTPUTS,
        input_files=_IDC_INPUTS,
        parser="textlayout.simulation.fastercap._parse_capacitance_matrix_pf",
        extraction_config={"term": "mutual", "matrix_index": [0, 1], "unit": "pF"},
        extract=_fastercap_mutual_pf,
        convergence=_fastercap_convergence,
    ),
    "02_cpw_50ohm": Recipe(
        component="CPW",
        analysis_scope="through_line_center_conductor",
        target_quantity="characteristic_impedance",
        target_value=50.0,
        target_unit="ohm",
        result_json="openems_result.json",
        output_files=("extraction/capacitance_input/openems_result.s2p",),
        input_files=(
            "extraction/capacitance_input/openems_model.json",
            "extraction/capacitance_input/openems_model.m",
        ),
        parser="textlayout.simulation.runners.extract_cpw_from_touchstone",
        extraction_config={"frequency_ghz": 6.0, "method": "symmetric_reciprocal_two_port"},
        extract=_cpw_impedance_ohm,
        convergence=_openems_convergence,
        superseded=SupersededClaim(
            status="CHARACTERISTIC_IMPEDANCE_EXTRACTED",
            extracted_value=49.88827755069874,
            extracted_unit="ohm",
            why_withdrawn=(
                "not reproducible from the committed openems_result.s2p. Re-extracting "
                "at the design frequency gives 49.712535 ohm; sample_frequency_ghz, "
                "s11_magnitude and return_loss_db all reproduce exactly, so the file and "
                "the parser agree and only this number is stale. No output hash existed "
                "at the time, so it cannot be established whether the Touchstone file or "
                "the impedance estimator changed."
            ),
        ),
    ),
    "03_idc_cpw_test_structure": Recipe(
        component="TestStructure",
        analysis_scope="embedded_idc_region_only",
        target_quantity="capacitance",
        target_value=0.6,
        target_unit="pF",
        result_json="extraction/capacitance_result.json",
        output_files=_IDC_OUTPUTS,
        input_files=_IDC_INPUTS,
        parser="textlayout.simulation.fastercap._parse_capacitance_matrix_pf",
        extraction_config={"term": "mutual", "matrix_index": [0, 1], "unit": "pF"},
        extract=_fastercap_mutual_pf,
        convergence=_fastercap_convergence,
        notes=(
            "FasterCap was run on the extracted IDC region only. The CPW launches "
            "and their transitions are not full-wave verified by this record.",
        ),
    ),
    "04_spiral_inductor_3nh": Recipe(
        component="SpiralInductor",
        analysis_scope="spiral_winding",
        target_quantity="inductance",
        target_value=3.0,
        target_unit="nH",
        result_json="extraction/capacitance_result.json",
        output_files=("extraction/capacitance_input/Zc.mat",),
        input_files=("extraction/capacitance_input/spiral.inp",),
        parser="textlayout.simulation.runners.parse_fasthenry_inductance",
        extraction_config={"frequency_hz": 1e6, "unit": "nH"},
        extract=_fasthenry_inductance_nh,
        convergence=_no_convergence,
    ),
    "05_quarter_wave_resonator_6ghz": Recipe(
        component="QuarterWaveResonator",
        analysis_scope="resonator_plus_coupler",
        target_quantity="resonance_frequency",
        target_value=6.0,
        target_unit="GHz",
        result_json="openems_result.json",
        output_files=("extraction/capacitance_input/openems_result.s2p",),
        input_files=(
            "extraction/capacitance_input/openems_model.json",
            "extraction/capacitance_input/openems_model.m",
        ),
        parser="textlayout.simulation.runners.extract_resonance_metrics_from_touchstone",
        extraction_config={"parameter": "s21", "edge_guard_bins": 2},
        extract=_resonance_ghz,
        convergence=_openems_convergence,
        superseded=SupersededClaim(
            status="RESONANCE_FREQUENCY_EXTRACTED",
            extracted_value=3.0,
            extracted_unit="GHz",
            why_withdrawn=(
                "3.0 GHz is the first point of the sweep, not a resonance. An argmin "
                "over all-NaN magnitudes returns index 0 because every NaN comparison "
                "is False, so the sweep's lower bound was reported as 'the resonance'."
            ),
        ),
    ),
    "06_research_test_chip": Recipe(
        component="TestChip",
        analysis_scope="full_tile",
        target_quantity="geometry",
        target_value=None,
        target_unit=None,
        analytical_only=True,
        analytical_model="per-sub-device analytical models",
        notes=(
            "No whole-tile field solve exists. Sub-block evidence (FasterCap IDC, "
            "FastHenry spiral) lives in tile_simulation_map.json and is scoped to "
            "those sub-blocks, never to the tile.",
        ),
    ),
}


def _git_commit(root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def _result_payload(showcase: Path, recipe: Recipe) -> dict[str, Any]:
    import json as _json

    if not recipe.result_json:
        return {}
    path = showcase / recipe.result_json
    if not path.is_file():
        return {}
    payload = _json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _analytical(showcase: Path, recipe: Recipe) -> tuple[float | None, str | None]:
    """The closed-form estimate this design was sized from.

    It is recorded next to the solver result, clearly labelled, because a reader
    comparing the two is the fastest way to notice that a solver result is wrong.
    """
    import json as _json

    result = _result_payload(showcase, recipe)
    value = result.get("analytical_value")
    model: str | None = None
    simulation = showcase / "simulation.json"
    if simulation.is_file():
        payload = _json.loads(simulation.read_text(encoding="utf-8"))
        for item in payload.get("evidence") or []:
            if isinstance(item, dict) and item.get("analytical_model"):
                model = str(item["analytical_model"])
                break
    return (float(value) if isinstance(value, (int, float)) else None), model


def build_canonical(
    showcase: Path, repo_root: Path, *, timestamp: str | None = None
) -> CanonicalEvidence:
    """Re-derive one showcase's canonical evidence from its committed outputs."""
    recipe = RECIPES[showcase.name]
    result = _result_payload(showcase, recipe)

    design_hash = sha256_file(showcase / "layout.json")
    gds = showcase / "output.gds"
    geometry_hash = sha256_file(gds) if gds.is_file() else None
    lock = repo_root / "uv.lock"
    environment_hash = sha256_file(lock) if lock.is_file() else None
    stamp = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")

    analytical_value, analytical_model = _analytical(showcase, recipe)
    common: dict[str, Any] = {
        "design_id": showcase.name,
        "design_hash": design_hash,
        "geometry_hash": geometry_hash,
        "component": recipe.component,
        "analysis_scope": recipe.analysis_scope,
        "target_quantity": recipe.target_quantity,
        "target_value": recipe.target_value,
        "target_unit": recipe.target_unit,
        "tolerance_percent": float(
            (result.get("target_comparison") or {}).get("tolerance_pct", 5.0)
        ),
        "git_commit": _git_commit(repo_root),
        "environment_hash": environment_hash,
        "timestamp": stamp,
        "warnings": list(result.get("warnings", [])),
        "analytical_value": analytical_value,
        "analytical_model": analytical_model,
    }

    if recipe.analytical_only:
        return CanonicalEvidence(
            evidence_id=compute_evidence_id(
                design_id=showcase.name,
                target_quantity=recipe.target_quantity,
                output_file_hashes={},
                extraction_config_hash=None,
            ),
            status=EvidenceStatus.ANALYTICAL_ONLY,
            warnings=[*common.pop("warnings"), *recipe.notes],
            **{**common, "analytical_model": recipe.analytical_model},
        )

    input_hashes = {
        name: sha256_file(showcase / name)
        for name in recipe.input_files
        if (showcase / name).is_file()
    }
    output_hashes = {
        name: sha256_file(showcase / name)
        for name in recipe.output_files
        if (showcase / name).is_file()
    }
    config_hash = sha256_json(recipe.extraction_config)
    evidence_id = compute_evidence_id(
        design_id=showcase.name,
        target_quantity=recipe.target_quantity,
        output_file_hashes=output_hashes,
        extraction_config_hash=config_hash,
    )

    assert recipe.extract is not None and recipe.convergence is not None
    convergence = recipe.convergence(showcase)

    solver_common: dict[str, Any] = {
        **common,
        "evidence_id": evidence_id,
        "solver_name": str(result.get("solver") or "unknown"),
        "solver_version": result.get("solver_version"),
        "command": [str(token) for token in result.get("command", [])],
        "return_code": result.get("return_code"),
        "runtime_seconds": result.get("runtime_seconds"),
        "input_file_hashes": input_hashes,
        "output_file_hashes": output_hashes,
        "parser": recipe.parser,
        "parser_version": PARSER_VERSION,
        "extraction_config": recipe.extraction_config,
        "extraction_config_hash": config_hash,
        "provenance_gaps": ["solver_executable_hash_unrecorded"],
        "superseded": recipe.superseded,
    }
    solver_common["warnings"] = [*solver_common.pop("warnings"), *recipe.notes]

    try:
        extracted = recipe.extract(showcase)
    except (ValueError, OSError) as exc:
        return CanonicalEvidence(
            status=EvidenceStatus.SIMULATION_INVALID,
            convergence=convergence,
            invalidation_reason=str(exc),
            **solver_common,
        )

    target = recipe.target_value
    error_percent = (
        (extracted - target) / abs(target) * 100.0
        if target is not None and target != 0
        else None
    )
    verified = (
        convergence.converged
        and error_percent is not None
        and abs(error_percent) <= solver_common["tolerance_percent"]
    )
    return CanonicalEvidence(
        status=EvidenceStatus.PHYSICS_VERIFIED if verified else EvidenceStatus.SIMULATION_EXECUTED,
        extracted_quantity=recipe.target_quantity,
        extracted_value=extracted,
        extracted_unit=recipe.target_unit,
        error_percent=round(error_percent, 6) if error_percent is not None else None,
        convergence=convergence,
        **solver_common,
    )
