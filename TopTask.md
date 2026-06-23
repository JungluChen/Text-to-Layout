/goal  You are a Principal AI-CAD and superconducting quantum EDA architect.

I want to refactor my project, Text-to-Layout / Text-to-GDS, by learning from:

1. earthtojake/text-to-cad
   https://github.com/earthtojake/text-to-cad

2. CADFusion paper
   "Text-to-CAD Generation Through Infusing Visual Feedback in Large Language Models"
   https://arxiv.org/pdf/2501.19054

Goal:
Do NOT keep building a fragile custom superconducting EDA tool from scratch.
Rebuild my project as a physics-grounded AI orchestration layer inspired by Text-to-CAD and CADFusion.

Core idea:
- Follow earthtojake/text-to-cad’s skill-based architecture:
  small reusable agent skills, explicit artifact generation, inspection, validation, viewer/export workflow.
- Follow CADFusion’s dual-signal idea:
  generation should be trained / guided by both parametric sequence correctness and rendered feedback.
- Adapt this to superconducting EDA:
  sequence signal = structured layout recipe / validated PCell parameters
  feedback signal = GDS render + DRC + extraction.json + solver evidence + physics checks

Do not hallucinate layout or physics.
Do not generate fake S-parameters, gain curves, bandwidth, noise, or quantum results.

============================================================
PART 1 — STUDY THE REFERENCE ARCHITECTURES
============================================================

Inspect earthtojake/text-to-cad and extract the design patterns:

- skill-based modular architecture
- plain-language request → structured artifact workflow
- generated file outputs
- viewer / inspection step
- validation before handoff
- clear separation between generation, rendering, validation, and export

Do not blindly copy mechanical CAD logic.
Extract the reusable agent architecture.

Study CADFusion and extract the training / feedback principle:

- sequential learning produces valid parametric sequences
- visual feedback evaluates rendered results
- many-to-one rendering means different sequences may produce similar valid outputs
- feedback should reward outputs that satisfy user intent better

Translate this to superconducting layout:

- sequential correctness:
  valid technology, valid layers, valid PCell parameters, valid netlist
- rendered correctness:
  GDS view, layer view, zoomed junction view, process stack view
- physics correctness:
  extraction.json, formula lineage, DRC, LVS, solver output
- feedback:
  rank candidate layouts by physical validity, manufacturability, and solver evidence

============================================================
PART 2 — CHANGE MY PROJECT ARCHITECTURE
============================================================

Refactor the project into a skill-based pipeline:

skills/
  intent/
  layout/
  render/
  drc/
  extraction/
  simulation/
  validation/
  report/

Each skill must:

1. Accept explicit input files.
2. Produce explicit output files.
3. Write a JSON status file.
4. Never silently invent missing data.
5. Be executable independently.
6. Be composable into a full workflow.

Example:

skills/intent:
  prompt.txt
  → design_intent.json

skills/layout:
  design_intent.json
  technology.yaml
  → device.gds
  → layout_metadata.json

skills/render:
  device.gds
  → full_layout.png
  → zoom_layout.png
  → layer_stack.png

skills/extraction:
  device.gds
  layout_metadata.json
  technology.yaml
  → extraction.json

skills/simulation:
  extraction.json
  device.gds
  → solver_input/
  → solver_output/
  → solver_status.json

skills/validation:
  extraction.json
  solver_output/
  → validation.json

skills/report:
  device.gds
  extraction.json
  validation.json
  solver_output/
  → physics_lineage_report.png
  → report.md

============================================================
PART 3 — REPLACE CUSTOM LAYOUT GENERATION
============================================================

Do not let the LLM directly draw arbitrary polygons.

Create a backend abstraction:

LayoutBackend:
  - name
  - supported_devices
  - generate(intent) -> GDS + metadata

Implement adapters for existing open-source frameworks where possible:

Priority:
1. KQCircuits for superconducting quantum layout
2. Qiskit Metal for superconducting qubit / microwave design
3. gdsfactory for generic GDS composition
4. existing local PCells only as fallback

Rules:
- The LLM chooses a backend and component type.
- The backend generates the layout.
- The LLM may tune parameters but cannot invent invalid layers or geometry.
- If no backend supports the requested device, return "unsupported", not fake layout.

============================================================
PART 4 — CREATE A SUPERCAD PARAMETRIC SEQUENCE FORMAT
============================================================

Inspired by CADFusion’s parametric sequence idea, create a text-based superconducting CAD sequence format:

Example:

DEVICE lumped_jpa
TECH ncu_nb_alox_v1

ADD cpw_feedline width=10um gap=6um length=500um layer=M1
ADD manhattan_jj area=0.05um2 jc=2uA/um2 layer_stack=M1/JJ/M2
ADD idc_capacitor target_c=1.2pF fingers=32 gap=2um
ADD flux_line distance=10um width=3um
ADD port name=in type=rf location=left impedance=50ohm
ADD port name=out type=rf location=right impedance=50ohm

CONSTRAINT target_f0=6GHz
CONSTRAINT min_spacing=2um
CONSTRAINT process=ncu_nb_alox_v1

This sequence must compile to:
- design_intent.json
- GDS
- metadata.json

This becomes the "sequential signal" for your project.

============================================================
PART 5 — ADD FEEDBACK / REPAIR LOOP
============================================================

Implement CADFusion-inspired feedback, but domain-specific.

For each prompt, generate N candidate sequences:

candidate_001.supercad
candidate_002.supercad
candidate_003.supercad

For each candidate:

1. Compile to GDS.
2. Render full layout and zoom views.
3. Run DRC.
4. Extract physical parameters.
5. Run available solver if configured.
6. Score the candidate.

Score components:

layout_score:
- no missing ports
- correct layer stack
- valid junction geometry
- reasonable spacing
- no obvious shorts

physics_score:
- all required extracted values exist
- Ic, Lj, C, L, f0 are physically valid
- formulas are within validity range

solver_score:
- real solver output exists
- Touchstone validated if RF result exists
- passivity and reciprocity checks pass

intent_score:
- target frequency error
- target impedance error
- target area / size constraints

Then select best candidate.

If all candidates fail:
return a failure report and do not fabricate fake results.

============================================================
PART 6 — MAKE FORMULA USE SAFE
============================================================

Every formula must be encoded as a method with a validity range.

Example:

Formula:
Lj = Phi0 / (2*pi*Ic)

Allowed only if:
- Ic comes from explicit Jc × extracted area, or measured Ic
- Ic > 0

Formula:
f0 = 1/(2*pi*sqrt(L*C))

Allowed only if:
- L and C are extracted or explicitly provided with source
- L > 0
- C > 0

Formula:
CPW Z0 conformal mapping

Allowed only as:
method = analytical_estimate

Not allowed as:
method = EM_solver

Create:

physics_methods.yaml

Each entry must include:
- equation
- assumptions
- required inputs
- invalid cases
- output units
- confidence level

============================================================
PART 7 — SOLVER BOUNDARY
============================================================

Separate estimate, extraction, simulation, and measurement:

estimated:
  analytical or rule-of-thumb value

extracted:
  derived from GDS geometry

simulated:
  produced by real solver output file

measured:
  imported from experiment data

Reports must label values clearly.

Never call estimated values simulated values.

Never call generated curves solver results unless they came from output files.

============================================================
PART 8 — DATASET / LEARNING ROADMAP
============================================================

Add a data folder inspired by CADFusion:

dataset/
  sequences/
    *.supercad
  renders/
    *.png
  extraction/
    *.json
  scores/
    *.json
  reports/
    *.md

Each example should store:
- prompt
- generated sequence
- GDS
- rendered layout
- extraction.json
- solver status
- score

This will let the project later train or fine-tune a model using:

1. sequential learning:
   prompt → supercad sequence

2. feedback learning:
   sequence + render + extraction + validation score

Do not train a model now unless requested.
First create the dataset structure and scoring pipeline.

============================================================
PART 9 — UPDATE EXAMPLES
============================================================

Rewrite examples so they follow the new workflow.

Required examples:

1. Manhattan Josephson junction
   prompt → supercad → GDS → area/Ic/Lj extraction → report

2. CPW quarter-wave resonator
   prompt → supercad → GDS → analytical estimate → optional openEMS → report

3. Lumped-element JPA seed
   prompt → supercad → GDS → extraction → JosephsonCircuits adapter if available → report

4. Failed solver example
   shows that missing solver output does not create fake curves

5. Candidate selection example
   generate 3 candidates and choose the best by score

============================================================
PART 10 — UPDATE README.md
============================================================

Rewrite README.md around this new positioning:

Title suggestion:
Physics-Grounded Text-to-GDS for Superconducting Quantum Circuits

README sections:

1. What this project is
   - AI orchestration layer for superconducting layout and validation

2. What this project is not
   - not a fake solver
   - not an LLM polygon generator
   - not a replacement for HFSS/KLayout/KQCircuits/Qiskit Metal

3. Architecture
   Prompt → SuperCAD sequence → validated layout backend → GDS render → extraction → solver → report

4. Inspired by
   - earthtojake/text-to-cad skill-based artifact workflow
   - CADFusion sequential + visual feedback idea

5. Workflow examples
   - JJ lineage
   - CPW resonator
   - failure when solver missing

6. Artifact contract
   Every skill produces:
   - output file
   - status JSON
   - validation result

7. How to run
   - install
   - generate one example
   - run all examples
   - run tests

8. Current limitations
   - openEMS/HFSS integration may be optional
   - formulas are estimates unless solver verified
   - fabrication readiness depends on selected backend/PDK

============================================================
PART 11 — RUN THE WHOLE WORKFLOW
============================================================

After editing, rerun:

pytest

python examples/run_all.py

python scripts/generate_assets.py

If using uv:

uv run pytest
uv run python examples/run_all.py
uv run python scripts/generate_assets.py

Return:
1. changed files
2. new folder structure
3. generated artifacts
4. failed examples and why
5. README.md diff
6. next recommended tasks

Do not only explain.
Edit the project directly.