"""CADFusion-style candidate generation and selection loop.

Implements the physics-compiler pipeline:

    prompt → target physics → N SuperCAD candidates
        for each candidate:
            compile()   → design_intent.json + GDS
            render()    → layout PNG
            extract()   → extraction.json (junction area, Ic, Lj, C, f0)
            validate()  → DRC + physics checks
            score()     → physics score (0-100)
        return best candidate

Failed candidates are stored alongside the winner so designs can be audited.
A candidate with status != "ok" is always stored and never silently dropped.

Score contract
--------------
score = 0         when technology YAML is missing or GDS generation failed
score = 0–49      when DRC or physics extraction failed
score = 50–79     when extraction passed but solver validation was skipped
score = 80–100    when all checks passed and solver validates physics
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = "text-to-gds.candidate-loop.v1"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CandidateSpec:
    """One SuperCAD sequence to try."""

    index: int
    supercad_text: str
    rationale: str = ""


@dataclass
class CandidateResult:
    """Result of evaluating one candidate through the pipeline."""

    index: int
    status: str = "pending"   # "ok" | "failed" | "unsupported" | "skipped" | "pending"
    reason: str | None = None
    supercad_text: str = ""
    design_intent_path: str | None = None
    gds_path: str | None = None
    extraction: dict[str, Any] = field(default_factory=dict)
    drc_passed: bool | None = None
    physics_passed: bool | None = None
    solver_status: str = "skipped"
    score: float = 0.0
    elapsed_s: float = 0.0
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class CandidateLoopResult:
    """Result of the full N-candidate loop."""

    schema: str = SCHEMA
    n_candidates: int = 0
    n_succeeded: int = 0
    n_failed: int = 0
    best_index: int | None = None
    best_score: float = 0.0
    winner: CandidateResult | None = None
    all_candidates: list[CandidateResult] = field(default_factory=list)
    elapsed_total_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "n_candidates": self.n_candidates,
            "n_succeeded": self.n_succeeded,
            "n_failed": self.n_failed,
            "best_index": self.best_index,
            "best_score": self.best_score,
            "winner": self.winner.to_dict() if self.winner else None,
            "all_candidates": [c.to_dict() for c in self.all_candidates],
            "elapsed_total_s": self.elapsed_total_s,
        }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_candidate(candidate: CandidateResult) -> float:
    """Assign a physics score 0–100 to one candidate."""
    if candidate.status in ("failed", "unsupported"):
        return 0.0

    score = 50.0

    # DRC
    if candidate.drc_passed is True:
        score += 10.0
    elif candidate.drc_passed is False:
        score -= 20.0

    # Physics extraction
    ext = candidate.extraction
    junc = ext.get("junction", {})
    lc = ext.get("linear_circuit", {})
    if junc.get("ic") is not None and junc.get("lj") is not None:
        score += 10.0
    if lc.get("resonance_frequency") is not None:
        score += 5.0
    if ext.get("validation", {}).get("passed"):
        score += 10.0

    # Solver
    if candidate.solver_status == "executed":
        score += 15.0
    elif candidate.solver_status == "failed":
        score -= 10.0

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _step_compile(
    spec: CandidateSpec,
    work_dir: Path,
    backend_name: str | None,
) -> CandidateResult:
    from textlayout._legacy.supercad import parse_supercad, compile_supercad

    start = time.monotonic()
    result = CandidateResult(index=spec.index, supercad_text=spec.supercad_text)
    try:
        sequence = parse_supercad(spec.supercad_text)
    except ValueError as exc:
        result.status = "failed"
        result.reason = f"SuperCAD parse error: {exc}"
        result.elapsed_s = time.monotonic() - start
        return result

    out = work_dir / f"candidate_{spec.index:02d}"
    out.mkdir(parents=True, exist_ok=True)
    compile_result = compile_supercad(sequence, output_dir=out, backend_name=backend_name)

    result.status = compile_result.get("status", "failed")
    result.reason = compile_result.get("reason")
    result.design_intent_path = compile_result.get("design_intent_path")
    result.gds_path = compile_result.get("gds_path")
    result.elapsed_s = time.monotonic() - start
    return result


def _step_extract(
    candidate: CandidateResult,
    jc_ua_per_um2: float | None,
) -> None:
    if candidate.status != "ok" or not candidate.gds_path:
        return
    gds = Path(candidate.gds_path)
    if not gds.is_file() or gds.stat().st_size == 0:
        return

    try:
        from textlayout._legacy.extraction import extract_physical_parameters

        sidecar_path = candidate.design_intent_path
        if sidecar_path and Path(sidecar_path).is_file():
            sidecar: dict[str, Any] = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
        else:
            sidecar = {"pcell": "unknown", "gds_path": str(gds), "info": {}, "ports": []}

        ext = extract_physical_parameters(gds, sidecar, jc_ua_per_um2=jc_ua_per_um2)
        candidate.extraction = ext
        candidate.physics_passed = ext.get("validation", {}).get("passed", False)
    except Exception as exc:  # noqa: BLE001
        candidate.extraction = {"error": str(exc)}
        candidate.physics_passed = False


def _step_drc(candidate: CandidateResult) -> None:
    if candidate.status != "ok" or not candidate.gds_path:
        candidate.drc_passed = None
        return
    gds = Path(candidate.gds_path)
    if not gds.is_file() or gds.stat().st_size == 0:
        candidate.drc_passed = None
        return
    try:
        from textlayout._legacy.drc import run_python_process_drc

        drc_result = run_python_process_drc(str(gds))
        candidate.drc_passed = drc_result.get("passed", False)
        candidate.artifacts["drc_report"] = json.dumps(drc_result)
    except Exception as exc:  # noqa: BLE001
        candidate.drc_passed = None
        candidate.artifacts["drc_error"] = str(exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_candidate_loop(
    specs: list[CandidateSpec],
    *,
    work_dir: str | Path,
    backend_name: str | None = None,
    jc_ua_per_um2: float | None = None,
    save_result: bool = True,
) -> CandidateLoopResult:
    """Run N candidates through the full compile → extract → validate → score loop.

    All candidates (including failures) are stored in *work_dir*.
    Returns a CandidateLoopResult with the best candidate and all candidates.

    Parameters
    ----------
    specs:
        List of CandidateSpec objects to evaluate.
    work_dir:
        Directory for all candidate artifacts.
    backend_name:
        Force a specific layout backend (None = auto-select).
    jc_ua_per_um2:
        Junction critical current density for extraction.
    save_result:
        Write the full loop result JSON to work_dir/candidate_loop_result.json.
    """
    loop_start = time.monotonic()
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    loop_result = CandidateLoopResult(n_candidates=len(specs))
    candidates: list[CandidateResult] = []

    for spec in specs:
        # 1. Compile
        c = _step_compile(spec, work, backend_name)

        # 2. Extract (only if compile succeeded and GDS is real)
        _step_extract(c, jc_ua_per_um2)

        # 3. DRC
        _step_drc(c)

        # 4. Score
        c.score = _score_candidate(c)

        candidates.append(c)

        # Save every candidate immediately — failures must be persisted
        candidate_json = work / f"candidate_{spec.index:02d}" / "candidate_result.json"
        candidate_json.parent.mkdir(parents=True, exist_ok=True)
        candidate_json.write_text(json.dumps(c.to_dict(), indent=2, default=str), encoding="utf-8")

    loop_result.all_candidates = candidates
    loop_result.n_succeeded = sum(1 for c in candidates if c.status == "ok")
    loop_result.n_failed = len(candidates) - loop_result.n_succeeded

    ok_candidates = [c for c in candidates if c.status == "ok"]
    if ok_candidates:
        winner = max(ok_candidates, key=lambda c: c.score)
        loop_result.winner = winner
        loop_result.best_index = winner.index
        loop_result.best_score = winner.score

    loop_result.elapsed_total_s = time.monotonic() - loop_start

    if save_result:
        result_path = work / "candidate_loop_result.json"
        result_path.write_text(
            json.dumps(loop_result.to_dict(), indent=2, default=str), encoding="utf-8"
        )

    return loop_result


# ---------------------------------------------------------------------------
# Convenience: generate N parameter variants from a base SuperCAD template
# ---------------------------------------------------------------------------

def _apply_param_sweep(
    template: str,
    param_name: str,
    values: list[str],
) -> list[CandidateSpec]:
    """Generate N SuperCAD variants by substituting one parameter."""
    specs: list[CandidateSpec] = []
    for i, val in enumerate(values):
        import re
        # Replace the param in the ADD line, e.g. trace_width=10.0um
        text = re.sub(
            rf"({param_name}=)[^\s]+",
            rf"\g<1>{val}",
            template,
        )
        specs.append(CandidateSpec(
            index=i,
            supercad_text=text,
            rationale=f"{param_name}={val}",
        ))
    return specs


def generate_cpw_frequency_sweep(
    technology: str,
    frequencies_ghz: list[float],
    trace_width_um: float = 10.0,
    gap_um: float = 6.0,
) -> list[CandidateSpec]:
    """Generate candidate CPW resonators sweeping over target frequencies.

    Uses the physics compiler to solve for electrical_length_um at each frequency,
    then wraps each solution in a SuperCAD sequence.
    """
    from textlayout._legacy.physics_compiler import solve_cpw_resonator

    specs: list[CandidateSpec] = []
    for i, f_ghz in enumerate(frequencies_ghz):
        solved = solve_cpw_resonator(
            target_frequency_ghz=f_ghz,
            effective_permittivity=6.2,
            resonator_mode=4,
            impedance_ohm=50.0,
        )
        if solved.status != "ok":
            continue
        params = solved.as_supercad_params()
        length_um = params.get("electrical_length_um", "5000um")
        tw = f"{trace_width_um}um"
        g = f"{gap_um}um"
        text = (
            f"DEVICE cpw_quarter_wave_resonator\n"
            f"TECH {technology}\n"
            f"ADD cpw_quarter_wave_resonator "
            f"target_frequency_ghz={f_ghz}GHz "
            f"electrical_length_um={length_um} "
            f"trace_width_um={tw} "
            f"gap_um={g}\n"
            f"CONSTRAINT target_frequency_ghz={f_ghz}GHz\n"
        )
        specs.append(CandidateSpec(
            index=i,
            supercad_text=text,
            rationale=f"CPW resonator at {f_ghz} GHz → L={length_um}",
        ))
    return specs
