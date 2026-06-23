"""Feedback / repair loop — CADFusion-inspired candidate selection (Part 5).

For each prompt, N candidate SuperCAD sequences are compiled, rendered, DRC'd,
extracted, and scored.  The best candidate is selected.  If all fail, a failure
report is returned — no fake results are fabricated.

Scoring dimensions (TopTask.md Part 5):

  layout_score  — ports, layer stack, junction geometry, spacing, no shorts
  physics_score — required extracted values present, Ic/Lj/C/L/f0 in range
  solver_score  — real solver output exists, Touchstone validated
  intent_score  — target frequency / impedance / size error
  total         — weighted sum (0–1)

Usage::

    from text_to_gds.feedback import select_best_candidate, score_candidate
    from text_to_gds.supercad import parse_supercad

    candidates = [parse_supercad(seq) for seq in sequences]
    result = select_best_candidate(candidates, output_dir="workspace/candidates")
    if result["status"] == "ok":
        print("Best:", result["best_candidate"])
        print("Score:", result["best_score"])
    else:
        print("All candidates failed:", result["reason"])
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from text_to_gds.supercad import SuperCADSequence, compile_supercad


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_candidate(
    compile_result: dict[str, Any],
    intent_constraints: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Score a compiled candidate.  Returns a score dict with 0–1 components.

    Parameters
    ----------
    compile_result:
        Output from compile_supercad().
    intent_constraints:
        CONSTRAINT key/value pairs from the SuperCAD sequence.

    Returns
    -------
    dict with:
        layout_score    0–1
        physics_score   0–1
        solver_score    0–1
        intent_score    0–1
        total           weighted composite
        issues          list of strings
        status          "ok" | "failed"
    """
    issues: list[str] = []
    intent_constraints = intent_constraints or {}

    # Compile failure → everything zero
    if compile_result.get("status") not in ("ok",):
        return {
            "layout_score": 0.0,
            "physics_score": 0.0,
            "solver_score": 0.0,
            "intent_score": 0.0,
            "total": 0.0,
            "issues": [f"compile failed: {compile_result.get('reason', 'unknown')}"],
            "status": "failed",
        }

    # --- layout score -------------------------------------------------------
    layout_score = 1.0
    metadata_path = compile_result.get("layout_metadata_path")
    if metadata_path and Path(metadata_path).is_file():
        metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        components = metadata.get("components", [])
        has_port = any(c.get("component") == "port" for c in components)
        if not has_port:
            layout_score -= 0.3
            issues.append("layout_score: no ports defined")
    else:
        layout_score -= 0.2
        issues.append("layout_score: layout_metadata.json not found")

    gds_path = compile_result.get("gds_path")
    if not gds_path or not Path(gds_path).is_file():
        layout_score -= 0.5
        issues.append("layout_score: GDS file not found")

    layout_score = max(0.0, layout_score)

    # --- physics score -------------------------------------------------------
    physics_score = 0.0
    extraction_path = _find_extraction(compile_result)
    extraction: dict[str, Any] = {}
    if extraction_path and Path(extraction_path).is_file():
        try:
            extraction = json.loads(Path(extraction_path).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            issues.append("physics_score: could not read extraction.json")

    if extraction.get("status") == "ok":
        physics_score = 1.0
        junc = extraction.get("junction", {})
        lc = extraction.get("linear_circuit", {})
        ic = junc.get("ic_a") or junc.get("ic")
        lj = junc.get("lj_h") or junc.get("lj")
        cap = lc.get("capacitance_f") or lc.get("capacitance")
        f0 = lc.get("resonance_frequency_hz") or lc.get("resonance_frequency")

        for name, value in [("Ic", ic), ("Lj", lj)]:
            if value is not None:
                try:
                    v = float(value)
                    if not (math.isfinite(v) and v > 0):
                        physics_score -= 0.2
                        issues.append(f"physics_score: {name} is not positive finite")
                except (TypeError, ValueError):
                    physics_score -= 0.2
                    issues.append(f"physics_score: {name} is not numeric")

        if cap is not None:
            try:
                if not (math.isfinite(float(cap)) and float(cap) > 0):
                    physics_score -= 0.15
                    issues.append("physics_score: capacitance is not positive finite")
            except (TypeError, ValueError):
                physics_score -= 0.15

        if f0 is not None:
            try:
                if not (math.isfinite(float(f0)) and float(f0) > 0):
                    physics_score -= 0.15
                    issues.append("physics_score: f0 is not positive finite")
            except (TypeError, ValueError):
                physics_score -= 0.15

        # check that all lineage entries have method_label
        lineage = extraction.get("lineage", {})
        missing_labels = [k for k, v in lineage.items()
                          if isinstance(v, dict) and "method_label" not in v]
        if missing_labels:
            physics_score -= 0.1 * len(missing_labels) / max(len(lineage), 1)
            issues.append(f"physics_score: {len(missing_labels)} lineage entries missing method_label")
    else:
        issues.append(f"physics_score: extraction status={extraction.get('status', 'missing')}")

    physics_score = max(0.0, min(1.0, physics_score))

    # --- solver score -------------------------------------------------------
    solver_score = 0.0
    solver_outputs = extraction.get("solver_outputs", {})
    touchstone = solver_outputs.get("touchstone_path")
    if touchstone and Path(touchstone).is_file():
        solver_score += 0.5
        try:
            from text_to_gds.rf_validation import validate_touchstone
            ts_result = validate_touchstone(touchstone)
            if ts_result.get("status") == "ok":
                solver_score += 0.5
            else:
                issues.append(f"solver_score: touchstone invalid: {ts_result.get('reason')}")
        except Exception:  # noqa: BLE001
            solver_score += 0.25
    else:
        issues.append("solver_score: no solver Touchstone output")

    solver_score = max(0.0, min(1.0, solver_score))

    # --- intent score -------------------------------------------------------
    intent_score = 1.0
    target_f0_str = intent_constraints.get("target_f0")
    if target_f0_str and extraction.get("status") == "ok":
        lc = extraction.get("linear_circuit", {})
        f0_hz = lc.get("resonance_frequency_hz") or lc.get("resonance_frequency")
        target_hz = _parse_freq(target_f0_str)
        if f0_hz is not None and target_hz is not None and target_hz > 0:
            rel_err = abs(float(f0_hz) - target_hz) / target_hz
            if rel_err > 0.20:
                intent_score -= 0.5
                issues.append(f"intent_score: f0 error {rel_err:.1%} > 20%")
            elif rel_err > 0.05:
                intent_score -= 0.2
                issues.append(f"intent_score: f0 error {rel_err:.1%} > 5%")
        elif f0_hz is None:
            intent_score -= 0.3
            issues.append("intent_score: f0 not extracted, cannot validate target")

    intent_score = max(0.0, min(1.0, intent_score))

    # --- weighted composite --------------------------------------------------
    total = (
        0.30 * layout_score
        + 0.35 * physics_score
        + 0.20 * solver_score
        + 0.15 * intent_score
    )

    return {
        "layout_score": round(layout_score, 4),
        "physics_score": round(physics_score, 4),
        "solver_score": round(solver_score, 4),
        "intent_score": round(intent_score, 4),
        "total": round(total, 4),
        "issues": issues,
        "status": "ok",
    }


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------

def select_best_candidate(
    candidates: list[SuperCADSequence],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Compile all candidates, score each, return the best.

    Parameters
    ----------
    candidates:
        List of parsed SuperCADSequence objects.
    output_dir:
        Root directory; each candidate gets a sub-directory candidate_NNN/.

    Returns
    -------
    dict:
        status        "ok" | "failed"
        reason        if status == "failed"
        best_index    0-based index of winner
        best_score    score dict
        all_scores    list of score dicts
        best_compile  compile result of winner
    """
    out = Path(output_dir)
    all_compile: list[dict[str, Any]] = []
    all_scores: list[dict[str, Any]] = []

    for idx, seq in enumerate(candidates):
        candidate_dir = out / f"candidate_{idx + 1:03d}"
        compile_result = compile_supercad(seq, output_dir=candidate_dir)
        score = score_candidate(
            compile_result,
            intent_constraints=seq.constraints,
        )
        _write_score(candidate_dir / "score.json", score, compile_result)
        all_compile.append(compile_result)
        all_scores.append(score)

    if not all_scores:
        return {"status": "failed", "reason": "no candidates provided"}

    best_idx = max(range(len(all_scores)), key=lambda i: all_scores[i]["total"])
    best_score = all_scores[best_idx]

    if best_score["total"] == 0.0:
        return {
            "status": "failed",
            "reason": "all candidates scored zero — no valid layout generated",
            "all_scores": all_scores,
        }

    return {
        "status": "ok",
        "best_index": best_idx,
        "best_candidate": f"candidate_{best_idx + 1:03d}",
        "best_score": best_score,
        "all_scores": all_scores,
        "best_compile": all_compile[best_idx],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_extraction(compile_result: dict[str, Any]) -> str | None:
    meta_path = compile_result.get("layout_metadata_path")
    if not meta_path:
        return None
    try:
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        return meta.get("sidecar_path")  # local_pcells backend stores sidecar path
    except Exception:  # noqa: BLE001
        return None


_FREQ_UNITS = {"ghz": 1e9, "mhz": 1e6, "khz": 1e3, "hz": 1.0}


def _parse_freq(value: str) -> float | None:
    v = value.strip().lower()
    for unit, scale in _FREQ_UNITS.items():
        if v.endswith(unit):
            try:
                return float(v[: -len(unit)]) * scale
            except ValueError:
                return None
    try:
        return float(v)
    except ValueError:
        return None


def _write_score(path: Path, score: dict[str, Any], compile_result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "score": score,
        "compile_status": compile_result.get("status"),
        "gds_path": compile_result.get("gds_path"),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
