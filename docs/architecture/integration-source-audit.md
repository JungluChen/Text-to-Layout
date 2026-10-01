# Integration source audit

**Document class: MANUAL_DOCUMENTATION.** Started 2026-09-26. This is a
source-and-scope audit of selected Priority 0 candidates, not installation,
platform, adapter or numerical validation. The 100-slot catalog intentionally
preserves user-supplied hints; corrections live here until a typed verified
source registry is specified.

| Slot | Source finding | Consequence |
| --- | --- | --- |
| 1 KQCircuits | [IQM's repository](https://github.com/iqm-finland/KQCircuits) describes a KLayout-based superconducting layout library and states GPL-3.0-or-later. | Canonical source and license identified. Import, geometry output, platform and solver behavior still need local checks. |
| 2 Qiskit Metal | The [maintainer repository](https://github.com/qiskit-community/qiskit-metal) now calls the project Quantum Metal, gives Apache-2.0, and says the current PyPI package is `quantum-metal`; the older `qiskit-metal` package is archived at a pre-v0.5 release. Its Ansys path requires AEDT and a license. | Audit the existing `layout` and newly declared `all` optional groups before migrating package names. Test imports and all platform locks in isolation; do not infer HFSS access from this package. |
| 3 pyEPR | The [maintainer repository](https://github.com/zlatko-minev/pyEPR) describes energy-participation quantization and its [license](https://github.com/zlatko-minev/pyEPR/blob/master/LICENSE) is BSD-3-Clause. Its canonical HFSS field-extraction example requires a live Ansys session, while the project also documents a no-HFSS numerical workflow. | Existing `src/textlayout/epr/backends.py` explicitly disables the live pyEPR/HFSS path; `_legacy/epr.py` can prepare a handoff. Treat an import or prepared script as neither licensed HFSS access nor executed EPR evidence. Audit the independent no-HFSS workflow before a typed adapter. |
| 4 CircuitQ | [PhilippAumann/circuitq](https://github.com/PhilippAumann/circuitq) is an MIT-licensed Python toolbox for symbolic Hamiltonian construction and numerical superconducting-circuit analysis; the maintainers link a [physics paper](https://doi.org/10.1088/1367-2630/ac8cab). | It is a circuit quantizer, not a 3D EM field solver. No current product adapter or numerical comparison was found in `src/textlayout`; pin a version and validate its equations/units against the paper before adding one. |
| 5 scqubits | [scqubits/scqubits](https://github.com/scqubits/scqubits) provides superconducting-qubit spectra and related calculations under its [BSD-3-Clause license](https://github.com/scqubits/scqubits/blob/main/LICENSE); its repository cites [Groszkowski and Koch (2021)](https://quantum-journal.org/papers/q-2021-11-17-583/). | The current `quantum` extra declares `scqubits>=4.0`, and `3799d8d` now executes a typed SI transmon model and retains spectra. Real execution is documented in `docs/progress/2026-09-28-012649.md`; convergence and independent reference agreement remain unestablished. This supersedes the earlier prepare-only observation; it does not complete acceptance. |
| 6 SQcircuit | The [project site](https://www.sqcircuit.org/) links to [stanfordLINQS/SQcircuit](https://github.com/stanfordLINQS/SQcircuit), which identifies BSD-3-Clause. The supplied `squadds/SQcircuit` hint is therefore not the canonical source shown by the maintainers. | Retain the original hint for provenance, but use the verified repository when evaluating versions, equations and examples. No local installation or calculation is certified. |
| 7 SQuADDS | The supplied `SQuADDS/SQuADDS` repository hint returned GitHub API 404 during this audit. The [maintainer repository](https://github.com/LFL-Lab/SQuADDS) identifies an MIT-licensed superconducting design database/workflow, cites its [2024 paper](https://doi.org/10.22331/q-2024-09-09-1465), and labels the software alpha. | Correct the source identity in a future typed registry while retaining the user hint for provenance. A published database and MCP server do not validate any Text-to-Layout adapter, geometry translation, solver run or numerical result. Audit dataset version, geometry/material compatibility and licensing before using reference rows. |
| 8 QEDA | [qeda/qeda](https://github.com/qeda/qeda) is a MIT-licensed Node.js tool for schematic symbols and PCB land patterns. The supplied URL resolves, but its documented function does not match the Quantum Chip EDA pillar's intended superconducting layout/physics role. | Reclassify or reject this slot during catalog deduplication; do not install it as a quantum solver or count it toward quantum-chip capability. |
| 9 PycQED | The supplied `DiCarloLab-Delft/PycQED` hint returned GitHub API 404. The group's [Python 3 repository](https://github.com/DiCarloLab-Delft/PycQED_py3) describes an MIT-licensed circuit-QED measurement environment built on QCoDeS, with instrument-specific setup rather than a standalone package. | Reclassify this as an optional measurement/calibration bridge, not an EM simulator or layout generator. Do not add hardware control to a base install or infer a usable measurement comparison without actual instrument/data provenance. |
| 10 Qiskit Dynamics | The [maintainer repository](https://github.com/qiskit-community/qiskit-dynamics) describes Apache-2.0 time-dependent quantum-system solvers with NumPy and optional JAX, but says it is no longer actively maintained; GitHub marks it archived. | Do not make an archived backend a default dependency. If a specific dynamics use case is needed, pin and test a compatible version, compare its differential-equation result with an independent reference, and assess maintained alternatives first. It is not an EM field solver. |
| 11 AWS Palace | The [maintainer repository](https://github.com/awslabs/palace) identifies Palace as an Apache-2.0 3D finite-element electromagnetic solver. The [official installation guide](https://awslabs.github.io/palace/stable/install/) recommends Spack and explains that Palace builds its own MFEM and libCEED. The repository pins Palace v0.17.0 / source commit `12d8069afb5aa9e169a17e303d735e120968e9f2` for its current benchmark. | Canonical source and declared license are identified. MFEM and libCEED inside Palace's build are dependencies, not separately validated slot 18 integrations. The actual v0.17.0 installation and smoke executed on the Linux CI runner, but the reduced resonator remains `SIMULATION_INVALID` at physical mode classification; do not count this slot as accepted, or infer Windows/macOS native operation. |
| 12 openEMS | The supplied [openEMS-Project](https://github.com/thliebig/openEMS-Project) is the umbrella repository; its [core solver](https://github.com/thliebig/openEMS) identifies GPL-3.0 and EC-FDTD, with CSXCAD providing geometry/material description. Do not confuse it with the unrelated OpenEMS energy-management project. | Existing `src/textlayout/simulation/` code has an openEMS adapter and evidence model, but source identity and a solver invocation alone do not establish geometry equivalence, FDTD convergence, or independent RF accuracy. Audit the core/CSXCAD dependency licenses and version pins before distribution. |
| 13 FasterCap | The supplied `FastFieldSolvers/FasterCap` hint returned GitHub API 404. [ediloren/FasterCap](https://github.com/ediloren/FasterCap) describes the capacitance extractor and declares LGPL-2.1-or-later in its README; GitHub detects LGPL-2.1. | The existing IDC adapter must be evaluated against this actual source, including solver executable identity, matrix signs/units, refinement and benchmark evidence. A prepared input or an executable probe is not an accepted integration; retain its separate numerical validation queue. |
| 14 FastHenry2 | The supplied `FastFieldSolvers/FastHenry2` hint returned GitHub API 404. [ediloren/FastHenry2](https://github.com/ediloren/FastHenry2) contains the original Unix FastHenry on `master`, a Windows FastHenry2 port on `WinMSVS`, and superconducting WRCad enhancements on another branch. GitHub's repository API reports no detected SPDX license. | Do not equate a free download or the separate LGPL-licensed FreeCAD workbench with permission to redistribute this solver. Audit the exact branch/source license terms and selected binary before any packaged dependency or accepted integration; distinguish FastHenry from FastHenry2 in adapter provenance and numerical benchmarks. |

| 15 Meep | [NanoComp/meep](https://github.com/NanoComp/meep) is an FDTD electromagnetic solver with Python, Scheme and C++ interfaces; upstream identifies GNU GPL and GitHub detects GPL-2.0. | The existing bridge is in the frozen legacy tree, not a new typed product integration. Audit dimensionless-to-SI conversion, material dispersion, PML and resolution/time convergence before any comparison. No Meep run was performed by this review. |
| 16 gprMax | [gprMax/gprMax](https://github.com/gprMax/gprMax) describes FDTD electromagnetic propagation and declares GPL-3.0-or-later. | No product adapter was found. Choose a bounded propagation or antenna reference first; validate grid spacing, timestep, sources and boundary effects. Upstream accelerator support is not evidence of Text-to-Layout platform support. |
| 17 Elmer FEM | [ElmerCSC/elmerfem](https://github.com/ElmerCSC/elmerfem) is the official multiphysics FEM suite. Its [component license policy](https://github.com/ElmerCSC/elmerfem/blob/devel/license_texts/ElmerLicensePolicy.md) distinguishes LGPL libraries from GPL tools/modules; GitHub detects NOASSERTION. | The existing electrostatic bridge is legacy. Audit the exact selected modules and dependency licenses instead of assigning one blanket SPDX license. A first product slice needs ElmerGrid conversion, electrode tags, Maxwell capacitance units/signs and a refined reference case. |
| 18 MFEM | [mfem/mfem](https://github.com/mfem/mfem) is a BSD-3-Clause finite-element library. | Palace already uses MFEM; that dependency is not a separate independent solver comparison. A direct integration would require its own weak formulation, boundary conditions, discretization, runner and reference evidence. Defer duplicate scaffolding. |
| 19 scuff-em | [HomerReid/scuff-em](https://github.com/HomerReid/scuff-em) supplies boundary-element EM applications. Its [COPYRIGHT](https://github.com/HomerReid/scuff-em/blob/master/COPYRIGHT) declares GPL-2.0-or-later; the repository also contains multiple license texts. | No product adapter was found. Surface mesh orientation, material model and integral-equation assumptions need explicit mapping. Audit component licenses and select a public electrostatic or scattering benchmark before installing. |
| 20 FEniCS | The supplied URL resolves to [FEniCS/dolfinx](https://github.com/FEniCS/dolfinx), the next-generation FEM environment, whose README declares LGPL-3.0-or-later. | Record DOLFINx explicitly rather than assuming compatibility with legacy DOLFIN APIs. No product adapter was found. A PDE library needs a specified formulation and manufactured/reference solution; an import cannot establish electromagnetic accuracy. |

These first twenty source reviews record the linked repositories' identity,
purpose and available license status at review time. FastHenry2's actual
source-license terms remain unverified. These reviews do not justify changing
`doctor.integration_targets[*].source_verified` globally or asserting that
the remaining supplied names resolve. Slot 21 is reviewed separately below.
Review remaining sources, aliases,
licenses and maintenance states in bounded groups before adding adapters.

## Revision snapshot for slots 15–20

GitHub API observations on 2026-09-27; all six reported `archived=false`.
These revisions identify the reviewed source, not an installed version or a
selected compatible release. Dependencies and platform execution are pending.

| Slot | Default branch | Observed commit |
| --- | --- | --- |
| 15 | master | `c830998c2553500719def730485cf479bca514ca` |
| 16 | master | `44dc76aa7b0dd6a5657fcb65fd5f8e91e4b851ca` |
| 17 | devel | `7a29c6258b6174c48c38778b7f8f14a7e53cbb8a` |
| 18 | master | `45799ebea86d9d83f027689ba2bcbd7e50f3021a` |
| 19 | master | `9c6d0cb7695463af803dee8d04cdae939740cdcc` |
| 20 | main | `120d1bcf1af6283a6ebefdad5e4e812789139578` |

## Slot 21: scikit-rf — 2026-09-28

Canonical source: [scikit-rf/scikit-rf](https://github.com/scikit-rf/scikit-rf).
Reviewed release v1.12.0 resolves to commit
`950534a5928d5c99e3fea2beaec7d82519800b0c`; the pinned
[LICENSE.txt](https://github.com/scikit-rf/scikit-rf/blob/950534a5928d5c99e3fea2beaec7d82519800b0c/LICENSE.txt)
is BSD-3-Clause. Upstream is not archived at review time. This is an RF network
analysis/model library, not an independent 3D field solver.

`uv.lock` already resolves scikit-rf 1.12.0 with NumPy, SciPy, pandas and
typing-extensions. The optional rf and solvers groups both reference this
same package; they are not two integrations. The base install remains lean.
Reviewed upstream revision, installed version and independent scientific
acceptance are separate facts.

The existing `cpw_skrf_z0` path uses the documented
[CPW model](https://scikit-rf.readthedocs.io/en/latest/api/media/generated/skrf.media.cpw.CPW.html):
width/gap/height converted from micrometres to metres, 1 GHz evaluation,
500 um substrate default, no metal backside and unspecified thickness.
The generator labels the height assumption, analytical method and confidence
0.65. Commit `a6f0406` implements selection; no second adapter is warranted.
For width 10 um, gap 6 um, eps_r 11.9, the installed library gives
50.0083038325503 ohm and effective permittivity 6.449543145912174. The fallback
returns 50.04115158403515 ohm and 6.45. Agreement with the same library tests
routing/units, not independent validation. Focused tests pass twice (2 each).

Next: specify a source-backed independent CPW case with matching substrate,
frequency, thickness and boundary assumptions; declare its uncertainty and
acceptance tolerance before evaluation. Keep slot 21 unchecked until its full
execution/reference/platform/commit contract is met. No new solver or MCP
capability is advertised by this audit. Reviewed slots now total 21; 79 remain.


## Slot 22: Qucs-S — 2026-10-02

Reviewed [release 26.1.1](https://github.com/ra3xdh/qucs_s/releases/tag/26.1.1)
at commit `b88d6fe20d3c0803507f38cc7fdef67c174a40ed`. The maintainer repository
is not archived at review time. The pinned
[README](https://github.com/ra3xdh/qucs_s/blob/b88d6fe20d3c0803507f38cc7fdef67c174a40ed/README.md)
describes a schematic/visualization front end for Ngspice (recommended), Xyce,
SpiceOpus and Qucsator. It derives from Qucs but is not the same repository.

[qucs/main.cpp](https://github.com/ra3xdh/qucs_s/blob/b88d6fe20d3c0803507f38cc7fdef67c174a40ed/qucs/main.cpp)
permits GPL-2.0-or-later; COPYING contains the GPL v2 text. Do not assign that
license automatically to all dependencies. The pinned .gitmodules contains
qucsator_rf, rxcalc and qucs-s-spar-viewer; exact gitlink revisions and source
file hashes are recorded in
[the audit record](../progress/evidence/2026-10-02-012737/qucs-source-audit.json).
Review each selected component's license before distribution.

The release build uses CMake and Qt6 (Core, Gui, Widgets and LinguistTools in
the top-level CMake file); README also lists Flex, Bison, gperf and dos2unix.
Ngspice is a separate runtime solver, not a Python package to add to the base
install. No Qucs-S adapter was found in src/textlayout; local PATH probes for
qucs-s and ngspice returned absent. This does not rule out installations outside
PATH. No installation, GUI execution, netlist export or simulation was tested.

**Deduplication:** slot 22 is the Qucs-S front end; slot 51 is ngspice, slot 52
is Xyce, and slot 59 is the original Qucs project. A Qucs-S run invoking ngspice
and a direct invocation of the same ngspice binary are not two independent
solver validations. Record both front-end revision/export hash and actual
solver identity/output hash. Do not inflate accepted counts by counting an
underlying engine twice.

**Next bounded slice:** audit documented netlist export/batch capabilities and
selected engine licensing, then specify a typed schematic/netlist handoff.
Start with an ideal RC small-signal AC circuit (explicit R in ohms, C in farads,
source amplitude/phase and output node), comparing complex transfer against
`H(jω)=1/(1+jωRC)`. Declare sweep, solver tolerances, precision/error budget and
acceptance before execution. This checks export, units and parser behavior;
it is not independent 3D RF accuracy or commercial parity. Keep this slot
unchecked until real execution, numerical and platform acceptance are retained.
