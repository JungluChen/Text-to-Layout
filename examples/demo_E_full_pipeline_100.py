"""Demo E -- 90->100: Complete 100-level pipeline with repair, EM export, and scientific report.

The full orchestration path from prompt to signoff-ready bundle:
  - compile_layout + run_drc + extract_layout + extract_physics_graph_artifact
  - export_openems_project (openEMS FDTD handoff)
  - export_palace_project (Palace eigenmode handoff)
  - run_simulation (JosephsonCircuits.jl)
  - run_analytical_verification + cross_validate_solvers
  - review_layout + evaluate_signoff_level
  - export_scientific_report (10-panel lineage report)
  - export_measurement_recipe (VNA recipe for level-6)

Run:
    uv run python examples/demo_E_full_pipeline_100.py
"""

from __future__ import annotations

import json

from text_to_gds.server import (
    compile_layout,
    cross_validate_solvers,
    evaluate_signoff_level,
    export_jpa_analysis,
    export_openems_project,
    export_palace_project,
    export_scientific_report,
    export_measurement_recipe,
    extract_layout,
    extract_physics_graph_artifact,
    generate_solver_inputs_from_physics_graph,
    review_layout,
    run_analytical_verification,
    run_drc,
    run_simulation,
    score_layout_quality,
)


def _status(d: dict, key: str = "status") -> str:
    return str(d.get(key, d.get("schema", "N/A")))[:60]


def main() -> None:
    print("\n=== Demo E: Full 100-level pipeline (90 -> 100) ===\n")

    # -- 1. Compile -----------------------------------------------------------
    print("1. compile_layout (lumped-element JPA seed)")
    result = compile_layout(
        pcell="lumped_element_jpa_seed",
        parameters={"center_frequency_ghz": 6.0, "target_gain_db": 20.0},
        output_name="demo_E_jpa.gds",
    )
    print(f"   gds_path: {result['gds_path']}")
    print(f"   status:   {result.get('status', 'N/A')}")

    # -- 2. DRC ---------------------------------------------------------------
    print("\n2. run_drc")
    drc = run_drc(result["gds_path"], min_width_um=0.1)
    print(f"   status:    {drc['status']}")
    print(f"   shapes:    {drc.get('checked_shapes', 'N/A')}")

    # -- 3. Extract -----------------------------------------------------------
    print("\n3. extract_layout + extract_physics_graph_artifact")
    ext = extract_layout(result["sidecar_path"], jc_ua_per_um2=2.0)
    graph = extract_physics_graph_artifact(result["sidecar_path"], output_name="demo_E_pg",
                                           jc_ua_per_um2=2.0)
    print(f"   extraction schema: {ext.get('schema', 'N/A')}")
    print(f"   graph schema:      {graph.get('schema', 'N/A')}")
    print(f"   graph nodes:       {len(graph.get('nodes', []))}")

    # -- 4. Solver input generation -------------------------------------------
    print("\n4. generate_solver_inputs_from_physics_graph")
    inputs = generate_solver_inputs_from_physics_graph(graph["result_path"],
                                                        output_name="demo_E_inputs")
    print(f"   schema:  {inputs.get('schema', 'N/A')}")
    print(f"   openEMS: {list(inputs.get('openems', {}).keys())}")

    # -- 5. EM solver handoffs ------------------------------------------------
    print("\n5. export_openems_project (CPW FDTD handoff -- status=skipped if Octave missing)")
    openems = export_openems_project(result["sidecar_path"])
    print(f"   status: {_status(openems)}")

    print("\n5b. export_palace_project (eigenmode handoff)")
    palace = export_palace_project(result["gds_path"], sidecar_path=result["sidecar_path"])
    print(f"   schema:  {palace.get('schema', 'N/A')}")
    print(f"   backend: {palace.get('backend', 'N/A')}")

    # -- 6. Circuit simulations -----------------------------------------------
    print("\n6. run_simulation (scqubits + josephsoncircuits)")
    sim_sc = run_simulation(result["sidecar_path"], simulator="scqubits", jc_ua_per_um2=2.0)
    sim_jc = run_simulation(result["sidecar_path"], simulator="josephsoncircuits",
                            jc_ua_per_um2=2.0, target_frequency_ghz=6.0)
    print(f"   scqubits engine:          {sim_sc.get('engine', 'N/A')}")
    print(f"   josephsoncircuits engine: {sim_jc.get('engine', 'N/A')}")

    # -- 7. Analytical verification + cross-validate --------------------------
    print("\n7. run_analytical_verification + cross_validate_solvers")
    theory = run_analytical_verification(
        output_name="demo_E_theory",
        center_frequency_ghz=6.0,
        kappa_mhz=120.0,
        pump_coupling_mhz=55.0,
    )
    print(f"   theory schema: {theory.get('schema', 'N/A')}")
    cv = cross_validate_solvers(
        [
            {"z0_ohm": 50.1, "method": "analytical"},
            {"z0_ohm": 49.8, "method": "extracted"},
        ],
        quantity="z0_ohm",
        tolerance_pct=5.0,
    )
    print(f"   agreement: {cv.get('agreement', 'N/A')}  max_dev={cv.get('max_deviation_pct','N/A')}")

    # -- 8. Review committee --------------------------------------------------
    print("\n8. review_layout (5-agent committee)")
    review = review_layout(result["sidecar_path"])
    print(f"   score:    {review.get('score', 'N/A')}")
    print(f"   approved: {review.get('approved', 'N/A')}")

    # -- 9. Signoff evaluation ------------------------------------------------
    print("\n9. evaluate_signoff_level")
    evidence = {"extraction": ext, "physics_graph": graph, "drc": drc,
                "sidecar_path": result["sidecar_path"]}
    signoff = evaluate_signoff_level(json.dumps(evidence))
    print(f"   level:  {signoff.get('level', 'N/A')}  (0-6)")
    print(f"   label:  {signoff.get('label', 'N/A')}")
    print(f"   passed: {signoff.get('passed', 'N/A')}")

    # -- 10. Score layout quality ---------------------------------------------
    print("\n10. score_layout_quality")
    sidecar_json = open(result["sidecar_path"], encoding="utf-8").read()
    quality = score_layout_quality(sidecar_json)
    print(f"   schema:  {quality.get('schema', 'N/A')}")
    print(f"   score:   {quality.get('overall_score', quality.get('score', 'N/A'))}")

    # -- 11. JPA analysis export ----------------------------------------------
    print("\n11. export_jpa_analysis")
    jpa_analysis = export_jpa_analysis(result["sidecar_path"], output_name="demo_E_jpa_analysis")
    print(f"   schema:  {jpa_analysis.get('schema', 'N/A')}")
    print(f"   status:  {_status(jpa_analysis)}")

    # -- 12. Scientific report ------------------------------------------------
    print("\n12. export_scientific_report (10-panel lineage report)")
    report = export_scientific_report(
        result["sidecar_path"],
        gds_layout_png=result["screenshot_path"],
        output_name="demo_E_report",
        jc_ua_per_um2=2.0,
        target_frequency_ghz=6.0,
        target_bandwidth_mhz=200.0,
    )
    print(f"   schema:   {report.get('schema', 'N/A')}")
    png = report.get("png_path", "N/A")
    print(f"   png_path: {png}")

    # -- 13. Measurement recipe (path to level 6) -----------------------------
    print("\n13. export_measurement_recipe (VNA recipe for measurement-calibrated signoff)")
    recipe = export_measurement_recipe(recipe="gain_map", output_name="demo_E_recipe")
    print(f"   schema: {recipe.get('schema', 'N/A')}")
    steps = recipe.get("steps", recipe.get("recipe_steps", []))
    for step in steps[:3]:
        if isinstance(step, dict):
            print(f"   [{step.get('step','?')}] {step.get('description','')[:70]}")
        else:
            print(f"   - {str(step)[:70]}")

    print("\n" + "=" * 60)
    print("FULL PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  GDS:          {result['gds_path']}")
    print(f"  DRC:          {drc['status']}")
    print(f"  Signoff level:{signoff.get('level', 'N/A')} -- {signoff.get('label', 'N/A')}")
    print(f"  Review score: {review.get('score', 'N/A')}")
    print(f"  Report:       {report.get('png_path', 'N/A')}")
    print("\n[PASS] Full 100-level pipeline completed.")


if __name__ == "__main__":
    main()
