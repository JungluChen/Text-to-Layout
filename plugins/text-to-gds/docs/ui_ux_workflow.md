# UI/UX Workflow

Text-to-GDS should feel like a local layout workbench, not a marketing page.
The current `run_design_workflow` output writes a local HTML workbench under
`workspace/artifacts/*.workbench.html`. The future live frontend should keep
the same structure and make the prompt/parameter panels executable from the
browser.

The live local server is available through:

```powershell
py -3 -m uv run python skills\text-to-gds\scripts\text_to_gds_tool.py ui --host 127.0.0.1 --port 8765
```

It serves a prompt form, output-name field, optimize checkbox, artifact links,
layout screenshot, generated workbench iframe, and raw JSON result.

The primary screen should be the active design session:

1. Prompt panel: user enters a request such as "Design a 5 GHz LJPA with wide
   bandwidth".
2. Clarification panel: show `plan_ljpa` questions for material, process stack,
   Jc, gain, bandwidth, noise, pump topology, and simulator.
3. Parameter panel: expose layout-sensitive values: layer, material, metal
   thickness, width, length, height/area, gap, angle, pitch, and turns.
4. Artifact panel: show generated `.gds`, `.layout.png`, `.sidecar.json`,
   `.drc.json`, `.extraction.json`, `.simulation.json`, and `.stack3d.html`.
5. Review panel: display the layout screenshot and 2.5D stack preview side by
   side, with DRC and simulation status kept visible.
6. Iterate command: rerun compile, DRC, extraction, preview, simulation, and
   optional surrogate optimization after any parameter change.

The first production UI should be dense, work-focused, and local-only. Avoid a
landing page as the first screen; make the design session the first screen.
