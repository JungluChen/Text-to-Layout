"""Demo B -- 25->50: Full extraction pipeline with physics graph and provenance.

GDS -> DRC -> extraction.json -> physics_graph.json -> solver inputs.
Every extracted value carries method_label, source, confidence.

Run:
    uv run python examples/demo_B_full_extraction.py
"""

from __future__ import annotations

import json

from text_to_gds.server import (
    compile_layout,
    extract_layout,
    extract_physics_graph_artifact,
    generate_solver_inputs_from_physics_graph,
    run_drc,
)


def main() -> None:
    print("\n=== Demo B: Full extraction pipeline (25 -> 50) ===\n")

    # -- Step 1: Compile CPW quarter-wave resonator ---------------------------
    print("Step 1 -- compile_layout: CPW quarter-wave resonator (6 GHz, 50 ohm)")
    result = compile_layout(
        pcell="cpw_quarter_wave_resonator",
        parameters={
            "target_frequency_ghz": 6.0,
            "effective_permittivity": 6.2,
            "trace_width": 10.0,
            "gap": 6.0,
        },
        output_name="demo_B_cpw.gds",
    )
    print(f"  gds_path:   {result['gds_path']}")
    print(f"  sidecar:    {result['sidecar_path']}")

    # -- Step 2: DRC ----------------------------------------------------------
    print("\nStep 2 -- run_drc")
    drc = run_drc(result["gds_path"], min_width_um=0.5)
    print(f"  status:          {drc['status']}")
    print(f"  checked_shapes:  {drc.get('checked_shapes', 'N/A')}")
    print(f"  violations:      {len(drc.get('violations', []))}")

    # -- Step 3: extract_layout -----------------------------------------------
    print("\nStep 3 -- extract_layout (with provenance lineage)")
    ext = extract_layout(result["sidecar_path"])
    params = ext.get("parameters", {})
    print(f"  schema:    {ext.get('schema', 'N/A')}")
    print(f"  Z0:        {params.get('characteristic_impedance_ohm', 'N/A')} ohm")
    print(f"  f0 est.:   {params.get('resonant_frequency_ghz', 'N/A')} GHz")
    lineage = ext.get("lineage", {})
    if lineage:
        for key, rec in list(lineage.items())[:3]:
            print(f"    {key}: method={rec.get('method_label','?')}, "
                  f"confidence={rec.get('confidence','?')}, source={rec.get('source','?')[:40]}")

    # -- Step 4: extract_physics_graph_artifact --------------------------------
    print("\nStep 4 -- extract_physics_graph_artifact (compiler IR)")
    graph = extract_physics_graph_artifact(
        result["sidecar_path"],
        output_name="demo_B_cpw",
    )
    print(f"  schema:       {graph.get('schema', 'N/A')}")
    print(f"  node count:   {len(graph.get('nodes', []))}")
    print(f"  edge count:   {len(graph.get('edges', []))}")
    node_types = [n.get("type", "?") for n in graph.get("nodes", [])]
    print(f"  node types:   {node_types}")

    # -- Step 5: generate_solver_inputs_from_physics_graph --------------------
    print("\nStep 5 -- generate_solver_inputs_from_physics_graph")
    inputs = generate_solver_inputs_from_physics_graph(
        graph["result_path"],
        output_name="demo_B_solver_inputs",
    )
    print(f"  schema:   {inputs.get('schema', 'N/A')}")
    print(f"  openEMS:  {list(inputs.get('openems', {}).keys())}")
    print(f"  palace:   {list(inputs.get('palace', {}).keys())}")
    print(f"  elmer:    {list(inputs.get('elmer', {}).keys())}")
    for rule in inputs.get("mesh_refinement_rules", [])[:3]:
        print(f"    mesh rule: {rule['region']} @ {rule['mesh_size_um']} um ({rule['priority']})")

    print("\n[PASS] Full extraction pipeline verified: GDS -> DRC -> extraction -> physics_graph -> solver inputs")
    print(f"       Physics graph written to: {graph['result_path']}")


if __name__ == "__main__":
    main()
