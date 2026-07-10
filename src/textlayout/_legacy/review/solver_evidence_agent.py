"""Solver evidence truthfulness reviewer.

Validates that solver execution claims are backed by real artifacts,
versions, and output files. Catches fabricated or placeholder results.
"""

from __future__ import annotations

from typing import Any

from textlayout._legacy.review.base import finding, review_result

_AGENT = "solver_evidence"


def _deep_search_source_llm(value: Any) -> bool:
    """Return True if any provenance record has source='LLM'."""
    if isinstance(value, dict):
        if str(value.get("source", "")).upper() == "LLM":
            return True
        return any(_deep_search_source_llm(v) for v in value.values())
    if isinstance(value, list):
        return any(_deep_search_source_llm(v) for v in value)
    return False


def _s_params_suspiciously_flat(sim: dict[str, Any]) -> bool:
    """Check whether S-parameter data is all zeros (placeholder)."""
    s_params = sim.get("s_parameters")
    if not isinstance(s_params, dict):
        return False
    s11 = s_params.get("S11") or s_params.get("s11")
    if not isinstance(s11, list) or len(s11) < 2:
        return False
    # All S11 magnitude values at exactly 0 dB is non-physical
    try:
        return all(float(v) == 0.0 for v in s11)
    except (TypeError, ValueError):
        return False


def review_solver_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Review solver evidence for truthfulness and completeness."""
    sim = evidence.get("simulation") or {}
    findings: list[dict[str, Any]] = []

    status = str(sim.get("status", "")).upper()

    # --- EXECUTED status requires proof artifacts ---
    if status == "EXECUTED":
        if not sim.get("solver_version"):
            findings.append(
                finding(
                    _AGENT,
                    "error",
                    "Simulation claims EXECUTED but no solver_version is recorded.",
                    "Record the solver name and version used for the run.",
                )
            )
        output_files = sim.get("output_files")
        if not isinstance(output_files, list) or len(output_files) == 0:
            findings.append(
                finding(
                    _AGENT,
                    "error",
                    "Simulation claims EXECUTED but output_files is missing or empty.",
                    "List all output artifacts produced by the solver.",
                )
            )
        runtime = sim.get("runtime_s")
        if runtime is not None:
            try:
                if float(runtime) <= 0:
                    findings.append(
                        finding(
                            _AGENT,
                            "error",
                            "Simulation runtime_s is <= 0, which is non-physical.",
                            "Record the actual wall-clock runtime from the solver.",
                        )
                    )
            except (TypeError, ValueError):
                findings.append(
                    finding(
                        _AGENT,
                        "warning",
                        f"Simulation runtime_s is not a valid number: {runtime!r}.",
                        "Record runtime as a numeric value in seconds.",
                    )
                )

        # EXECUTED with no parsed quantities is suspicious
        parsed = sim.get("parsed_quantities")
        if not parsed:
            findings.append(
                finding(
                    _AGENT,
                    "warning",
                    "Simulation is EXECUTED but no parsed_quantities were extracted.",
                    "Extract key results from the solver output files.",
                )
            )

    # --- Gain data requires a nonlinear Josephson solver ---
    if sim.get("gain_db") is not None:
        engine = str(sim.get("solver_version", "") or sim.get("engine", "")).lower()
        adapter = str(sim.get("adapter", "")).lower()
        has_jc_proof = any(
            kw in source
            for source in (engine, adapter)
            for kw in ("josephsoncircuits", "josim")
        )
        if not has_jc_proof and status != "SKIPPED":
            findings.append(
                finding(
                    _AGENT,
                    "error",
                    "Gain data (gain_db) present without JosephsonCircuits.jl or JoSIM execution proof.",
                    "Run a nonlinear Josephson solver or remove gain_db.",
                )
            )

    # --- S-parameter flatness check ---
    if sim.get("s_parameters") and _s_params_suspiciously_flat(sim):
        findings.append(
            finding(
                _AGENT,
                "error",
                "S-parameters are suspiciously flat (all S11 = 0 dB), likely placeholder data.",
                "Run a real EM solver to produce physical S-parameter results.",
            )
        )

    # --- Touchstone path validation ---
    touchstone = sim.get("touchstone_path")
    if touchstone is not None:
        ts_str = str(touchstone)
        if not (ts_str.endswith(".s2p") or ts_str.endswith(".s1p")):
            findings.append(
                finding(
                    _AGENT,
                    "error",
                    f"touchstone_path does not end in .s2p or .s1p: {ts_str!r}.",
                    "Ensure the Touchstone file has the correct extension.",
                )
            )

    # --- source="LLM" in any provenance record ---
    if _deep_search_source_llm(evidence):
        findings.append(
            finding(
                _AGENT,
                "error",
                'A provenance record has source="LLM", which is invalid.',
                "Replace LLM-sourced values with solver or analytical results.",
            )
        )

    # --- SKIPPED is valid ---
    if status == "SKIPPED":
        reason = sim.get("reason") or sim.get("skip_reason") or "no reason given"
        findings.append(
            finding(
                _AGENT,
                "info",
                f"Simulation honestly SKIPPED: {reason}.",
                "",
            )
        )

    # --- FAILED requires investigation ---
    if status == "FAILED":
        fail_reason = sim.get("reason") or sim.get("error") or "unknown failure"
        findings.append(
            finding(
                _AGENT,
                "error",
                f"Simulation FAILED: {fail_reason}.",
                "Investigate the solver failure before signoff.",
            )
        )

    return review_result(_AGENT, findings)
