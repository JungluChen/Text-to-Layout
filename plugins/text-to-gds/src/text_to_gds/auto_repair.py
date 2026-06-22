"""Auto-repair loop: generate -> review -> fix until the committee accepts.

The loop is a bounded harness driven by two callbacks so it stays solver- and
generator-agnostic:

    generate_fn(state) -> evidence   # produce review evidence from a design state
    repair_fn(state, committee) -> state  # return a *new* state addressing blockers

It stops when the committee approves with a score at/above ``threshold``, when
the iteration budget is exhausted, or when ``repair_fn`` returns an unchanged
state (no progress). It never reports acceptance while any reviewer has an error,
because acceptance requires ``committee['approved']`` (no errors) as well as the
score threshold.
"""

from __future__ import annotations

from typing import Any, Callable

from text_to_gds.review.committee import review_committee


def run_auto_repair(
    initial_state: dict[str, Any],
    generate_fn: Callable[[dict[str, Any]], dict[str, Any]],
    repair_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    *,
    threshold: int = 90,
    max_iterations: int = 6,
) -> dict[str, Any]:
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")

    state = dict(initial_state)
    history: list[dict[str, Any]] = []

    for iteration in range(1, max_iterations + 1):
        evidence = generate_fn(state)
        committee = review_committee(evidence)
        history.append(
            {
                "iteration": iteration,
                "score": committee["score"],
                "approved": committee["approved"],
                "error_count": committee["error_count"],
                "blockers": [b["finding"] for b in committee["blockers"]],
            }
        )

        if committee["approved"] and committee["score"] >= threshold:
            return {
                "schema": "text-to-gds.auto-repair.v1",
                "accepted": True,
                "iterations": iteration,
                "final_score": committee["score"],
                "final_committee": committee,
                "final_state": state,
                "history": history,
            }

        next_state = repair_fn(state, committee)
        if next_state == state:
            break  # repair made no progress; stop rather than loop forever
        state = next_state

    return {
        "schema": "text-to-gds.auto-repair.v1",
        "accepted": False,
        "iterations": len(history),
        "final_score": history[-1]["score"] if history else 0,
        "final_committee": review_committee(generate_fn(state)),
        "final_state": state,
        "history": history,
        "reason": "iteration budget exhausted or repair stalled before reaching threshold",
    }
