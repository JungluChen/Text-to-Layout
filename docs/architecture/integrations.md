# Integration boundary and candidate inventory

**Document class: MANUAL_DOCUMENTATION.** Decision recorded 2026-09-26.
This describes the first inventory slice; it does not certify a solver or a
platform.

The shared `textlayout` DSL, geometry, technology and evidence models remain
the authority for every client. A candidate integration consumes typed inputs
from that core. It may discover an external tool without running it, prepare
inputs, execute a pinned tool, parse solver-owned outputs, and submit results
to the existing evidence contract. A successful import, executable version
probe or process exit cannot promote numerical evidence. The current
`textlayout.solvers.base.SolverAdapter` already specifies these operations;
new adapters should satisfy it or document a necessary contract change rather
than introduce a second competing protocol.

`src/textlayout/integrations/targets.json` preserves the user's 100 numbered
candidate slots in ten pillars. Names and source hints are unverified request
data, including commercial bridges, possible aliases, and projects without
upstream references. `load_targets()` checks catalog structure only. The
`simulation/backends` namespace is reserved; importing it registers and
executes nothing. Existing solver adapters stay in their current locations
until one migration can be validated against actual inputs and outputs.

`textlayout doctor --json` reports this list in `integration_targets`, separate
from `external_solvers`. Eight exact candidate/check matches carry existing
version or import probes. The other 92 say `NOT_PROBED`. Every entry says
`source_verified=false`, `license_verified=false`, and
`execution_verified=false`. A `FOUND` probe has its own narrow scope; it is
not a license, platform, convergence or scientific validation claim. The
catalog is not exposed as 100 callable MCP tools.

The added optional groups in `pyproject.toml` cover only currently declared
Python dependencies. Empty `spice`, `vlsi`, `commercial` and `ai` groups do not
install native tools or grant commercial licenses. The `all` group describes
the declared research Python stack, not all candidates. The existing core
dependency set is unchanged. A genuinely lean/headless base requires its own
dependency migration and full compatibility gates.

For each candidate before implementation: verify canonical upstream and
license, distinguish aliases and bridges from engines, pin a compatible
version/hash, record supported hosts, define quantities and units, identify
existing code, and select a public benchmark with an independently justified
tolerance. A first adapter slice then needs discovery tests, absent-tool
behavior, solver-owned inputs/outputs and logs, convergence, canonical
evidence, CLI exposure, platform CI and a guidebook example. Keep the Palace
candidate isolated until its real Linux benchmark passes those gates.
