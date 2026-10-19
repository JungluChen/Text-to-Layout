# SQuADDS — entry 007 audit

Document class: MANUAL_DOCUMENTATION. Entry remains unchecked.

## Source identity and licenses

Official code repository: https://github.com/LFL-Lab/SQuADDS . Inventory hint
SQuADDS/SQuADDS must not be treated as verified source. Latest release observed
v0.4.5 points to beace3e52ceb491b8ef85b7e3f5439cb8273f248; its LICENSE is MIT.
The tag pyproject.toml declares version 0.4.4, reproduced by a second fetch at
that exact commit with identical bytes. PyPI metadata reports 0.4.5. Do not
silently equate tag, wheel and declared package version. Next compare the
published wheel/source hashes and import version before choosing a runtime.
Retained source/dependency/license metadata: ../progress/evidence/2026-10-13-162826/.

The upstream methods paper is Quantum 8, 1465 (2024),
https://doi.org/10.22331/q-2024-09-09-1465 . A citation is not electrical agreement.
The existing reference checker pins a separate HuggingFace dataset revision
0e25705f54c343fb96571ff15b6fd8375ca899aa (MIT dataset card) and WM1 design
revision 5329ff178980c16a299caa4804a2e5251e326833. It records no license file
for that pinned GDS repository; do not conflate code/dataset/design licenses
or vendor the GDS based on the SQuADDS code license.

## Dependencies and deduplication

Release metadata requires Python >=3.10, NumPy >=1.16.6,<2, pandas >=1.5,<3,
datasets >=4.8.1, scipy, scqubits, pyepr-quantum, scikit-rf and numerous
visualization/data packages. Required dependencies also include pyaedt==0.23,
quantum-metal>=0.5.0, PySide6>=6.10.1, Streamlit and Gmsh. These overlap entries
002, 003 and 005 but do not make those whole projects accepted or make SQuADDS
a duplicate target. NumPy <2 conflicts with the isolated SQcircuit runtime's
NumPy 2.5.3; use separate environments if package execution is needed. Do not
add this dependency stack to the lean base. An ANSYS client package is not
commercial solver access, which remains unavailable.

## Existing integration and evidence

`src/textlayout/external/squadds_mcp.py` is a frozen SquaddsPrior dataclass that
serializes PRIOR_ONLY and physics_verified=false. It has unannotated-unit float
maps and no live MCP connection or schema discovery. Reuse or tighten this
boundary; do not describe it as a working host integration.

`src/textlayout/verification/squadds_reference.py` already fetches hash-pinned
WM1 dataset/GDS assets and round-trips all four top variants. Retained repeated
results in docs/progress/evidence/2026-09-15-051619 report mask_geometry_passed,
four variants and six published measurement records. Device-to-top mapping is
null, electrical_reproduction_status is NOT_EVALUATED and error percent null.
This is mask import/export evidence, not a regenerated design or reproduced
measurement. Eight existing test_public_reference.py tests passed this audit;
no fresh geometry/solver execution or platform certification was performed.

At the pinned upstream source, squadds_mcp/server.py registers database,
analysis, interpolation, contribution and generation groups; startup constructs
SQuADDS_DB with network activity documented in source. Static wiring is not a
verified tools/list response. Host schemas, callable examples and installation
remain pending; contribution tools must not be invoked implicitly.

## Next bounded slice and acceptance

First reconcile release/wheel identity and select a hash-pinned, explicitly
licensed dataset slice. Prefer an offline typed prior importer with explicit
units, source revision, record identity and provenance; preserve PRIOR_ONLY.
Define deterministic selection/tie handling and malformed-data tests before
adding live retrieval. Reuse the existing WM1 geometry checker where relevant.
Acceptance requires actual repeated execution, independently checked dataset
selection/provenance, platform evidence and implementation commit. Electrical
validation additionally needs matched fabricated variant, stack/materials,
ports/junctions and converged extraction paired with measurements. Entry 007
remains unchecked until a bounded scope satisfies those criteria.

## Published artifact identity reconciliation (2026-10-13-235906)

Two downloads of each PyPI 0.4.5 archive matched the published SHA256:
wheel b0b9ef9dcff843c26577bab9dd57801aaa533dcc388535392c09b9d0646e7c2f;
sdist 906dc94b8aa98954c0b37a55fc07b077c7e9fc2639614428890c8f25fa4e9695.
All 107 package files present in the sdist match the wheel and pinned tag
byte-for-byte. The tag and sdist LICENSE match. The complete pyproject diff
is the version change 0.4.4 to 0.4.5; wheel METADATA, sdist PKG-INFO and the
static package __version__ declaration all say 0.4.5. This resolves the
observed metadata discrepancy without assuming tag packaging is identical.
Retained member hashes, requirements, archive URLs and comparison results:
../progress/evidence/2026-10-13-235906/identity.json. Archives remain outside Git.
No package import, install or upstream execution was performed. Runtime
compatibility remains untested. A future isolated runtime should pin the
published wheel hash above and verify installed metadata separately.
Next define the offline dataset-prior scope, explicit units and provenance;
keep upstream-package execution distinct from a local dataset importer.

## Offline WM1 frequency loader

The existing prior boundary now exposes load_wm1_prior for exact device selection
from hash-pinned local bytes. It imports only F_res_GHz, F_01_GHz and signed
Anharmocity_MHz into Hz, retaining the original fields and conversion metadata.
Repeated local execution on all six published records matched independently
transcribed values exactly. This is data-conversion evidence, not prediction,
SQuADDS package execution or electrical agreement. Entry 007 remains unchecked;
CLI, upstream tool execution where required and platform acceptance are pending.

### Dedicated prior-data platform benchmark

The manual `squadds-prior-integration` workflow uses Python 3.12 and the frozen
core environment on Windows, macOS and Linux. It downloads only the pinned
dataset, executes all six CLI selections twice, and checks expected Hz, source
identity, PRIOR_ONLY and identical repeats. It retains source bytes, command
records, stdout/stderr, runtime identity and hashes. No upstream SQuADDS package
or solver runs. Workflow existence is not platform acceptance: download and
independently inspect all packets after a successful exact-SHA run. On failure,
preserve the artifact and rerun unchanged before editing; never promote a
partial packet or omit a failed platform.

## Upstream helper execution audit (2026-10-18)

Pinned wheel member `squadds/core/db_devices.py` executed unchanged in a
standalone namespace against the pinned dataset twice, with identical output.
All three measured-device metadata projections match an independent direct
projection; WM1 simulation configuration identifiers match source strings.
These are identifiers, not numerical simulation results. Package import,
SQuADDS_DB construction and MCP were not executed. This narrowly establishes
helper execution only, not installed-package or platform acceptance.

Observed provenance discrepancy reproduced unchanged: WM1 top-level foundry
and find_reference_device_info report SQUILL, while
find_device_contributor_info reports N/A because it reads contrib_info.foundry.
Preserve source-level placement rather than treating N/A as absent fabrication
provenance. No upstream or product code was patched.

Static constructor audit: SQuADDS_DB.__init__ invokes supported_config_names,
which calls load_supported_config_names. That calls delete_HF_cache and
get_dataset_config_names with force_redownload. Cache deletion uses a path
built from expanduser('~') (and a distinct Windows path), so HF_HOME alone
is insufficient isolation. Normal package import eagerly imports Analyzer
and database code despite the lazy AnsysSimulator export.

Next: resolve a pinned optional runtime separately, then run normal package
import and constructor with a disposable OS user/home and explicit dataset
revision policy. Do not monkeypatch constructor/network calls and describe
that as normal package execution. Retain failures, versions and cache effects;
repeat unchanged before adding a typed upstream execution adapter. Entry 007
remains unchecked. Evidence: ../progress/evidence/2026-10-18-224826/.

## macOS normal-import compatibility probe (2026-10-19)

A binary-only Python 3.12 macOS ARM64 resolution of the pinned 0.4.5 wheel
installed 135 distributions and passed uv pip check, but normal import failed
twice: PyArrow 26.0.0 requires NumPy >=2 at runtime, whereas SQuADDS requires
NumPy <2 (resolved 1.26.4). Metadata compatibility is insufficient.

Adding explicit pyarrow==21.0.0 produced a 134-distribution candidate and
normal import passed twice on macOS 26.6.2 ARM64/Python 3.12.14. Installed and
imported SQuADDS versions both equal 0.4.5; stdout matched byte-for-byte.
This constraint also changes datasets (5.1.0 to 5.0.1), Hugging Face Hub
(2.2.0 to 1.33.0), fsspec and HTTP dependencies. The entire resolved set,
not PyArrow alone, is the tested environment. Hash manifests, both failed
traces, both successful probes and dependency differences are retained in
../progress/evidence/2026-10-19-114302/. No base dependency was changed.

This is normal package import evidence only. SQuADDS_DB was not constructed;
no dataset retrieval, electrical computation or MCP call was performed.
Windows/Linux runtime compatibility remains untested. Next use a disposable
user home for constructor/cache effects and define a revision-pinned dataset
execution contract. Entry 007 remains unchecked.

## Installed-package offline data execution (2026-10-19 follow-up)

Normal `squadds.core.db_devices` import in the retained compatible runtime now
executes against a real `datasets.Dataset.from_list` built from the hash-pinned
local source. The installed helper bytes match the pinned wheel member exactly.
Two unchanged runs passed independent projection checks for all three measured
device metadata records, WM1 configuration-identifier lookup, reference lookup
and absent-name behavior. Output JSON is byte-identical, with empty logs.
The SQUILL/N/A foundry discrepancy reproduces through normal package imports.

Evidence: ../progress/evidence/2026-10-19-160828/. Versions: SQuADDS 0.4.5,
datasets 5.0.1, PyArrow 21.0.0, NumPy 1.26.4 and pandas 2.3.3. Full resolved
runtime remains pinned in the preceding 114302 packet. No constructor override
or fake module was used. SQuADDS_DB was not constructed; its forced retrieval
and cache deletion were not invoked. Simulation configuration strings remain
identifiers, not numerical results or electrical evidence.

Next bounded implementation can expose this offline metadata projection via an
isolated typed adapter, requiring explicit pinned local input and verifying
installed source identity. Reject changed source/schema and preserve the
upstream discrepancy rather than silently filling fields. Before acceptance,
retain repeated normal-package execution on Windows/Linux as well as macOS.
Live database retrieval still needs a separately specified revision/cache
contract; it need not be invoked for this offline helper scope. Entry stays open.
