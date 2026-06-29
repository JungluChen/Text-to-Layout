"""Demo D -- 75->90: Review committee + signoff evaluation.

Runs the full 5-agent review committee over a compiled JPA layout and evaluates
the signoff level. Demonstrates:
  - review_layout: 5-agent committee (physics/microwave/fab/measurement/literature)
  - evaluate_signoff_level: level 0-6 determination
  - export_measurement_plan: what to measure to reach level 6
  - validate_device_template: schema validation

Score = minimum across all reviewers. A single error blocks approval.
Pass threshold = 90.

Run:
    uv run python examples/demo_D_review_and_signoff.py
"""

from __future__ import annotations

import json

from text_to_gds.server import (
    compile_layout,
    evaluate_signoff_level,
    export_measurement_plan,
    extract_layout,
    extract_physics_graph_artifact,
    review_layout,
    run_drc,
    run_simulation,
    validate_device_template,
)


def main() -> None:
    print("\n=== Demo D: Review committee + signoff (75 -> 90) ===\n")

    # -- Step 1: Compile and extract -----------------------------------------
    print("Step 1 -- compile_layout + extract_layout")
    result = compile_layout(
        pcell="lumped_element_jpa_seed",
        parameters={"center_frequency_ghz": 6.0, "target_gain_db": 20.0},
        output_name="demo_D_jpa.gds",
    )
    drc = run_drc(result["gds_path"], min_width_um=0.1)
    ext = extract_layout(result["sidecar_path"], jc_ua_per_um2=2.0)
    graph = extract_physics_graph_artifact(result["sidecar_path"], output_name="demo_D_pg")
    sim = run_simulation(result["sidecar_path"], simulator="scqubits", jc_ua_per_um2=2.0)
    print(f"  DRC status:   {drc['status']}")
    print(f"  extraction:   {ext.get('schema', 'N/A')}")
    print(f"  physics_graph:{graph.get('schema', 'N/A')}")
    print(f"  simulation:   {sim.get('status', sim.get('schema', 'N/A'))}")

    # -- Step 2: review_layout -- 5-agent committee --------------------------
    print("\nStep 2 -- review_layout (5-agent committee)")
    review = review_layout(result["sidecar_path"])
    print(f"  score:    {review.get('score', 'N/A')}  (min across all 5 reviewers)")
    print(f"  approved: {review.get('approved', 'N/A')}")
    print(f"  passed:   {review.get('passed', 'N/A')}  (threshold = 90)")
    reviewers = review.get("reviewers", {})
    for name, r in reviewers.items():
        icon = "+" if r.get("passed") else "X"
        findings = r.get("findings", [])
        n_err = sum(1 for f in findings if f.get("severity") == "error")
        n_warn = sum(1 for f in findings if f.get("severity") == "warning")
        print(f"  [{icon}] {name:<15} score={r.get('score','N/A'):>3}  errors={n_err} warnings={n_warn}")

    blocking = review.get("blocking_issues", [])
    if blocking:
        print(f"\n  Blocking issues ({len(blocking)}):")
        for b in blocking[:5]:
            print(f"    - {b}")

    # -- Step 3: evaluate_signoff_level --------------------------------------
    print("\nStep 3 -- evaluate_signoff_level")
    evidence = {
        "extraction": ext,
        "physics_graph": graph,
        "drc": drc,
        "sidecar_path": result["sidecar_path"],
    }
    signoff = evaluate_signoff_level(json.dumps(evidence))
    print(f"  level:   {signoff.get('level', 'N/A')}  (0=geometry, 5=physics signoff, 6=measured)")
    print(f"  label:   {signoff.get('label', 'N/A')}")
    print(f"  passed:  {signoff.get('passed', 'N/A')}")
    blockers = signoff.get("blockers", [])
    if blockers:
        print(f"  blockers ({len(blockers)}):")
        for b in blockers[:4]:
            print(f"    - {b}")

    # -- Step 4: validate_device_template ------------------------------------
    print("\nStep 4 -- validate_device_template")
    vdt = validate_device_template(result["sidecar_path"], device="jpa")
    print(f"  schema:  {vdt.get('schema', 'N/A')}")
    print(f"  valid:   {vdt.get('valid', 'N/A')}")

    # -- Step 5: export_measurement_plan -- what to do next ------------------
    print("\nStep 5 -- export_measurement_plan (next actions to reach level 6)")
    mplan = export_measurement_plan(result["sidecar_path"], output_name="demo_D_plan")
    print(f"  schema:  {mplan.get('schema', 'N/A')}")
    steps = mplan.get("steps", mplan.get("measurement_steps", []))
    for step in steps[:3]:
        if isinstance(step, dict):
            print(f"    [{step.get('step','?')}] {step.get('description','')[:70]}")
        else:
            print(f"    - {str(step)[:70]}")

    print("\n[PASS] Review committee + signoff verified.")
    print(f"       Committee score: {review.get('score', 'N/A')}")
    print(f"       Signoff level:   {signoff.get('level', 'N/A')} -- {signoff.get('label', 'N/A')}")


if __name__ == "__main__":
    main()
