# Reference architecture review

**Reviewed:** 2026-08-04  
**Scope:** open-source layout, PDK, numerical electromagnetics, and
superconducting-circuit projects relevant to Text-to-Layout.

This review records architectural ideas, not permission to promote a prepared
input or analytical estimate into solver evidence. Text-to-Layout keeps its
typed design intent, deterministic geometry, canonical evidence contract, and
signoff gates as the integration boundary. External projects remain optional,
process-isolated backends with solver-owned outputs and explicit provenance.

## Decisions at a glance

| Reference | Most useful pattern | Text-to-Layout decision |
| --- | --- | --- |
| gdsfactory | Parametric components, ports, cross-sections, PDK activation, GDS regression | Keep gdsfactory as the geometry kernel; add process-qualified cells through explicit PDKs rather than global defaults. |
| quantum-rf-pdk (QPDK) | Quantum/RF PDK organization, CPW routes, layer stack, test chips | Reuse public components only through pinned, provenance-recorded adapters; do not treat a reusable PCell as foundry qualification. |
| KQCircuits | KLayout PCells, mask/layer configuration, simulation objects, containerized development | Adopt separation between layout elements and simulation objects; do not duplicate its application framework. |
| Qiskit Metal | QDesign/QComponent/renderers/analyses separation | Preserve geometry-versus-analysis boundaries; require real exported comparison artifacts before interoperability can pass. |
| KLayout | Hierarchical database, scripted DRC, PCells | Use it for deterministic readback and rule execution; do not make interactive GUI state part of reproducibility. |
| SQuADDS | Versioned simulated/measured design data, inverse-design priors, contribution provenance | Model external designs as `PRIOR_ONLY` until regenerated and independently verified locally. |
| SQDMetal | Qiskit Metal/GDS to Gmsh to Palace pipeline | Adapt the explicit geometry-mesh-solver handoff and artifact checks; exclude COMSOL paths from production. |
| Palace | Mesh plus JSON problem definition, multiple EM problem types, convergence and field outputs | Keep a thin adapter and archive resolved config, mesh, logs, tables, and convergence; never reimplement FEM. |
| openEMS | EC-FDTD, explicit mesh/boundaries/ports, time-domain termination, Touchstone output | Validate the complete runtime stack and physical port setup, then require parsed finite S-parameters and convergence diagnostics. |
| FasterCap / FastHenry | Focused electrostatic and magnetoquasistatic extraction with iterative convergence | Keep them as narrow independent quantity extractors with refinement histories and solver-owned files. |
| JoSIM | RCSJ transient netlists, reusable parameters, sweeps, deterministic seed support | Use for time-domain JJ circuits with explicit junction/environment records and parsed transient outputs. |
| JosephsonCircuits.jl | Frequency-domain harmonic balance, S-parameters, noise | Treat as an optional independent nonlinear backend after a real circuit-model builder exists. |
| scqubits | Lumped Hamiltonians, spectra, matrix elements, parameter sweeps | Use only after EM/circuit extraction and only for quantization-scoped claims. |

## Layout and PDK projects

### gdsfactory

- **Architecture and data model:** Python parametric components expose named
  ports; cross-sections and a PDK bind geometry to layers, cells, and routing
  behavior. Hierarchical GDS cells remain the exchange artifact.
- **Algorithms and interface:** geometry construction, routing, boolean
  operations, and KLayout-backed verification are layout algorithms, not EM
  solvers. Text-to-Layout should pass typed parameters into registered cells and
  retain port/layer metadata in its sidecar.
- **Testing and reproducibility:** use deterministic settings serialization,
  GDS regression/diff tests, and fixed technology activation. Pin the package
  and record its version in generated evidence.
- **Adopt:** ports, cross-sections, explicit PDK activation, cell registries,
  hierarchical composition, and geometry regression.
- **Do not copy:** mutable global technology state as hidden input, or the idea
  that successful GDS generation establishes electrical correctness.
- **License:** MIT; retain notices when redistributing source or adapted cells.
  Sources: [gdsfactory documentation](https://gdsfactory.github.io/gdsfactory/),
  [PDK guide](https://gdsfactory.github.io/gdsfactory/notebooks/08_pdk/),
  [repository and license](https://github.com/gdsfactory/gdsfactory).

### quantum-rf-pdk (QPDK)

- **Architecture and data model:** a gdsfactory PDK groups quantum/RF cells,
  routes, cross-sections, a layer map/stack, analytical models, and test-chip
  composition.
- **Algorithms and interface:** parametric CPW, resonator, qubit, and packaging
  cells feed the ordinary gdsfactory component interface. Analytical models are
  initializers or sanity checks, not numerical signoff.
- **Testing and reproducibility:** component GDS regression plus model/netlist
  validation; installation and technology selection are explicit.
- **Adopt:** public CPW routing conventions, cross-section objects, test-chip
  composition, and component-level regression fixtures where their provenance
  and layer semantics match.
- **Do not copy:** generic material/process values into a fabrication claim, or
  import the entire catalog before core benchmarks close.
- **License:** MIT; individual contributed data or referenced foundry rules need
  separate provenance review. Sources: [QPDK documentation](https://gdsfactory.github.io/quantum-rf-pdk/),
  [cell catalog](https://gdsfactory.github.io/quantum-rf-pdk/cells.html),
  [repository](https://github.com/gdsfactory/quantum-rf-pdk).

### KQCircuits

- **Architecture and data model:** KLayout-native Elements/PCells compose chips;
  technology files define layers and masks; simulation objects are separated
  from layout elements and exported to solver-specific workflows.
- **Algorithms and interface:** KLayout PCell evaluation and mask generation are
  kept apart from simulation setup. The project exposes standalone scripts and
  container-oriented developer flows.
- **Testing and reproducibility:** deterministic PCell parameter tests,
  geometry snapshots, CI, and pinned container environments reduce desktop
  KLayout drift.
- **Adopt:** element/simulation separation, explicit technology loading, mask
  export checks, and container recipes for difficult optional solvers.
- **Do not copy:** its full GUI/application framework, project-wide inheritance
  hierarchy, or process-specific mask assumptions.
- **License:** GPL-3.0; importing or adapting implementation code can impose
  copyleft obligations. Prefer subprocess/interchange boundaries unless the
  distribution strategy is intentionally GPL-compatible. Sources:
  [KQCircuits documentation](https://iqm-finland.github.io/KQCircuits/),
  [standalone development](https://iqm-finland.github.io/KQCircuits/developer/standalone.html),
  [repository and license](https://github.com/iqm-finland/KQCircuits).

### Qiskit Metal

- **Architecture and data model:** `QDesign` holds chips, variables, components,
  and geometry tables; `QComponent` creates geometry and pins; renderers and
  analyses consume the design without becoming the design.
- **Algorithms and interface:** renderers translate a common design into
  external formats or solvers; analysis objects manage setup and results.
- **Testing and reproducibility:** component options, geometry tables, and
  renderer configuration can be serialized, but installed external tools and
  version pins still must be recorded by the caller.
- **Adopt:** clean separation of design, component, renderer, and analysis;
  comparable port/layer/connectivity exports for interoperability tests.
- **Do not copy:** renderer APIs for commercial solvers into the required
  production path, or pandas geometry tables as a second source of truth.
- **License:** Apache-2.0. Sources: [Qiskit Metal tutorials](https://qiskit-community.github.io/qiskit-metal/tut/index.html),
  [repository and license](https://github.com/qiskit-community/qiskit-metal).

### KLayout

- **Architecture and data model:** hierarchical cells, shapes, layers, PCells,
  regions, and netlist/database APIs; DRC scripts operate on selected layers and
  emit explicit violation databases.
- **Algorithms and interface:** robust geometric operations, hierarchical
  readback, width/space/enclosure checks, and scripted batch execution.
- **Testing and reproducibility:** run headless scripts against fixed GDS/OASIS
  and technology inputs; archive rule deck, version, invocation, and report.
- **Adopt:** KLayout readback as independent geometry evidence and scripted DRC
  as the rule-execution boundary.
- **Do not copy:** GUI session state or a generic deck presented as foundry DRC.
- **License:** GPL-3.0 for KLayout; use is compatible with a local tool workflow,
  while distribution/linkage choices require license review. Sources:
  [DRC manual](https://www.klayout.de/doc/manual/drc_basic.html),
  [PCell manual](https://www.klayout.de/doc/manual/pcell.html),
  [repository](https://github.com/KLayout/klayout).

## Validated quantum-design projects

### SQuADDS

- **Architecture and data model:** versioned design/simulation datasets connect
  geometry, Hamiltonian quantities, provenance, and contributed measured-device
  context. Search, interpolation, and inverse-design tools operate over those
  records.
- **Algorithms and interface:** nearest/design-space search and interpolation
  produce candidates or priors; Palace integration can regenerate EM results.
  A database record is not proof for a newly generated local layout.
- **Testing and reproducibility:** dataset version, contribution metadata,
  simulation configuration, code revision, and per-dataset licensing are
  material inputs.
- **Adopt:** immutable design IDs, simulation/measurement linkage, contribution
  provenance, uncertainty fields, and `PRIOR_ONLY` inverse-design candidates.
- **Do not copy:** a cloud/database runtime requirement, silent interpolation
  outside a validated domain, or promotion of a neighboring design's result.
- **License:** code is MIT; contributed datasets can carry their own terms and
  must be reviewed record by record. Sources: [SQuADDS documentation](https://lfl-lab.github.io/SQuADDS/),
  [developer guide](https://lfl-lab.github.io/SQuADDS/source/developer/index.html),
  [repository](https://github.com/LFL-Lab/SQuADDS).

### SQDMetal

- **Architecture and data model:** Qiskit Metal or layout geometry is converted
  into a 3-D Gmsh model, assigned materials/boundaries/ports, and solved by
  Palace for capacitance, eigenmode, driven, or EPR-style analyses.
- **Algorithms and interface:** mesh construction is a distinct step from the
  Palace JSON problem and result parsing. That separation makes artifacts and
  failure ownership auditable.
- **Testing and reproducibility:** preserve geometry, `.msh`, resolved Palace
  configuration, solver version, logs, and result tables; compare physical
  quantities, not screenshots.
- **Adopt:** the explicit layout-to-mesh-to-solver pipeline and analysis-specific
  setup objects.
- **Do not copy:** COMSOL-dependent paths, implicit desktop state, or a second
  geometry source of truth.
- **License:** Apache-2.0. Sources: [Palace simulation guide](https://sqdlab.github.io/SQDMetal/simulations/simpalace.html),
  [repository and license](https://github.com/sqdlab/SQDMetal).

## Electromagnetics projects

### Palace

- **Architecture and data model:** an external mesh plus a declarative JSON
  problem defines electrostatic, magnetostatic, eigenmode, driven, or transient
  finite-element analyses, boundary attributes, materials, solver tolerances,
  and output directories.
- **Algorithms and interface:** high-order parallel FEM with PETSc/MFEM-based
  linear/eigen solvers, optional adaptivity, and field/table outputs. Palace owns
  the numerical solve; the Python adapter should only prepare, invoke, validate,
  and parse.
- **Testing and reproducibility:** archive the exact mesh, resolved JSON,
  executable/container identity, logs, convergence history, and output tables;
  demonstrate mesh or polynomial-order convergence for claimed quantities.
- **Adopt:** thin process isolation, explicit boundary/material validation,
  analysis-specific parsers, and convergence gates.
- **Do not copy:** FEM kernels, preconditioners, or a broad mirror of Palace's
  schema inside Text-to-Layout.
- **License:** Apache-2.0. Sources: [Palace quick start](https://awslabs.github.io/palace/stable/quick/),
  [problem types](https://awslabs.github.io/palace/stable/config/problem/),
  [postprocessing](https://awslabs.github.io/palace/stable/config/postprocess/),
  [repository](https://github.com/awslabs/palace).

### openEMS and CSXCAD

- **Architecture and data model:** CSXCAD defines materials and geometry;
  openEMS consumes the mesh, boundaries, excitations, and ports for an
  equivalent-circuit FDTD solve. Python or Octave interfaces prepare the model;
  solver output is postprocessed into port quantities and Touchstone data.
- **Algorithms and interface:** EC-FDTD with nonuniform Cartesian meshing,
  absorbing boundaries, port excitation, time-domain decay/termination, and
  frequency-domain S-parameter extraction.
- **Testing and reproducibility:** official examples check the complete runtime
  stack, not only one executable. Preserve XML/model input, mesh summary,
  boundary/port definitions, solver log/end criterion, raw port files, and
  parsed finite/passive S-parameters.
- **Adopt:** full-stack discovery, physical CPW port validation, mesh refinement,
  and raw-to-Touchstone traceability.
- **Do not copy:** random example scripts without their physical assumptions, or
  accept a launch success as convergence.
- **License:** openEMS is GPL-3.0-or-later and CSXCAD is LGPL-3.0-or-later;
  subprocess use keeps ownership clear, while redistributed modifications must
  comply with their licenses. Sources: [openEMS documentation](https://docs.openems.de/),
  [Python interface](https://docs.openems.de/python/openEMS/openEMS.html),
  [installation check](https://docs.openems.de/install/check.html),
  [repository](https://github.com/thliebig/openEMS-Project).

### FasterCap and FastHenry

- **Architecture and data model:** both are focused field extractors driven by
  geometry/material input files. FasterCap returns capacitance matrices from a
  boundary-element formulation; FastHenry returns frequency-dependent
  resistance/inductance or impedance data from conductor filaments.
- **Algorithms and interface:** accelerated boundary-element electrostatics and
  multipole-accelerated magnetoquasistatic PEEC, respectively. Iterative solver
  tolerance and geometry discretization are part of the result.
- **Testing and reproducibility:** pin source/version and build recipe; archive
  input deck, executable identity, stdout/stderr, output matrix, units, and at
  least two refinements with a declared relative-change threshold.
- **Adopt:** one-quantity adapters, strict matrix parsers, refinement histories,
  and independent analytical/cross-solver checks.
- **Do not copy:** solver internals, object/build artifacts as executables, or a
  single coarse result promoted to convergence.
- **License:** FasterCap is distributed as open source under LGPL terms by its
  vendor; the commonly used FastHenry source distribution is permissively
  licensed. Pin exact archives and include their license files rather than
  relying on a family-name assumption. Sources: [FasterCap product/source page](https://www.fastfieldsolvers.com/fastercap.htm),
  [FastHenry overview](https://www.fastfieldsolvers.com/fasthenry2.htm),
  [FastHenry source mirror](https://github.com/ediloren/FastHenry2).

## Superconducting-circuit projects

### JoSIM

- **Architecture and data model:** SPICE-like netlists describe Josephson
  junctions, passive elements, transmission lines, sources, parameters, and
  output requests.
- **Algorithms and interface:** time-domain modified nodal analysis of RCSJ
  circuits, including sweeps/noise where configured. Results must be parsed from
  JoSIM-owned output, not reconstructed from target values.
- **Testing and reproducibility:** reusable netlists, explicit `.PARAM` values,
  pinned version, fixed noise seed, solver log, timestep/window, and CSV traces.
- **Adopt:** typed netlist generation, explicit junction/environment records,
  deterministic seeds, transient sanity checks, and parameter sweeps.
- **Do not copy:** a generic gain formula in place of nonlinear dynamics, or
  infer missing junction parameters from placeholder polygons.
- **License:** the pinned JoSIM v2.7 source is MIT, not GPL. Registry metadata is
  tested against that pin. Sources: [JoSIM repository](https://github.com/JoeyDelp/JoSIM),
  [v2.7 license](https://raw.githubusercontent.com/JoeyDelp/JoSIM/v2.7/LICENSE).

### JosephsonCircuits.jl

- **Architecture and data model:** Julia circuit/network objects represent
  linear elements, Josephson nonlinearities, pumps, ports, and frequency grids;
  result arrays include harmonic-balance operating points and linearized
  scattering/noise quantities.
- **Algorithms and interface:** frequency-domain harmonic balance with analytic
  Jacobians followed by linearized S-parameter/noise analysis. This complements,
  rather than replaces, JoSIM's time-domain solve.
- **Testing and reproducibility:** pin the Julia project/manifest; preserve the
  generated circuit, pump/frequency grid, tolerances, package version, logs, and
  result arrays; verify residual convergence and energy/passivity constraints in
  the applicable regime.
- **Adopt:** optional process-isolated frequency-domain backend and independent
  nonlinear cross-validation.
- **Do not copy:** package internals, unpinned Julia environments, or claim
  execution from the current prepared-only driver.
- **License:** MIT. Sources: [JosephsonCircuits.jl repository](https://github.com/kpobrien/JosephsonCircuits.jl),
  [package documentation](https://juliapackages.com/p/josephsoncircuits).

### scqubits

- **Architecture and data model:** circuit classes and custom symbolic circuits
  build lumped Hamiltonians; Hilbert spaces and parameter sweeps produce energy
  spectra, matrix elements, dispersive quantities, and noise estimates.
- **Algorithms and interface:** numerical diagonalization and basis truncation
  for quantum circuits. These outputs are downstream of extracted lumped
  parameters and are not electromagnetic field solutions.
- **Testing and reproducibility:** record component model, Hamiltonian, units,
  basis/truncation settings, parameter grid, scqubits version, convergence under
  cutoff increase, and output arrays.
- **Adopt:** typed component-specific Hamiltonian builders, truncation
  convergence, and spectrum/matrix-element evidence scoped to quantization.
- **Do not copy:** notebook state, broad component coverage before validation,
  or use a spectrum as evidence for EM convergence or fabrication readiness.
- **License:** BSD-3-Clause. Sources: [parameter-sweep guide](https://scqubits.readthedocs.io/en/latest/guide/parametersweep/ipynb/paramsweep.html),
  [custom-circuit guide](https://scqubits.readthedocs.io/en/latest/guide/circuit/ipynb/custom_circuit.html),
  [repository](https://github.com/scqubits/scqubits).

## Integration rules derived from the study

1. `physics_graph.json` and the typed design intent remain the local source of
   truth. Upstream records are priors or comparison artifacts, never silent
   replacements.
2. Geometry, meshing, solving, parsing, convergence, comparison, and signoff are
   separate stages with separately owned artifacts.
3. Every external backend must report discovery, exact identity/version,
   command, inputs, logs, solver-owned output, parser result, and convergence.
4. A prepared file, importable package, found binary, or successful process exit
   is not numerical evidence.
5. Parameterized cells require layer/process provenance and regression tests;
   reusable geometry is not a fabrication-qualified PDK.
6. SQuADDS-style records enter as versioned priors. Only regenerated geometry
   and local solver/measurement evidence can advance signoff.
7. JoSIM, JosephsonCircuits.jl, and scqubits have distinct physical scopes:
   transient nonlinear circuits, frequency-domain nonlinear circuits, and
   lumped Hamiltonian quantization.
8. GPL components stay behind local executable/interchange boundaries unless a
   deliberate distribution-license decision says otherwise. Every pinned
   archive retains its exact upstream license and notice.

