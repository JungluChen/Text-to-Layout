# Third Party Notices

This file is generated from `external_tools/registry.toml`.
It records upstream license metadata and integration policy; it is not legal advice.

Commercial solver binaries, license files, and proprietary libraries must not be committed.
GPL tools are kept in separate processes or environments with file-exchange adapters unless reviewed separately.

## Palace

- Upstream: https://github.com/awslabs/palace
- Pinned ref: `v0.17.0`
- Resolved commit: `12d8069afb5aa9e169a17e303d735e120968e9f2`
- Source archive SHA-256: `169f7fe210ea6e771a29bfe0803dd84a774b25b00d2aa3a1f33b9d97a510ff9d`
- SPDX license identifier: `Apache-2.0`
- Copyright holder: Amazon.com, Inc. or its affiliates
- Install mode: pinned source build or pinned container
- Integration mode: external executable via subprocess and file exchange
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.solvers.palace.backend`
- Dataset license: not_applicable
- Human review required: false

## Gmsh

- Upstream: https://gitlab.onelab.info/gmsh/gmsh
- Pinned ref: `gmsh_4_15_2`
- Resolved commit: `657c8e915f60405e6cad0c8ec7faf812bfff1a60`
- Source archive SHA-256: `9c743bcddc5199bbcb9ee5aaf333a47d2c450e6157b042716c549650a990dcd9`
- SPDX license identifier: `GPL-2.0-or-later`
- Copyright holder: Christophe Geuzaine and Jean-Francois Remacle
- Install mode: uv optional dependency group mesh; external GPL runtime, source not vendored into the MIT package
- Integration mode: external GPL mesh runtime producing .msh files for process-isolated file exchange with Palace
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.mesh.runtime`
- Dataset license: not_applicable
- Human review required: false

## ParaView

- Upstream: https://github.com/Kitware/ParaView
- Pinned ref: `v5.13.3`
- Resolved commit: `33274c1e71474b91721a41e3c449277d1e67d1ae`
- Source archive SHA-256: `9089d61f5928cd20ff90218b6e77a02f08690ca75518cab96f455dc86fc7a719`
- SPDX license identifier: `BSD-3-Clause`
- Copyright holder: ParaView contributors and Kitware, Inc.
- Install mode: isolated official binary extraction under .tools/paraview
- Integration mode: external pvpython executable via subprocess and file exchange
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.solvers.palace.paraview`
- Dataset license: not_applicable
- Human review required: false

## JosephsonCircuits.jl

- Upstream: https://github.com/kpobrien/JosephsonCircuits.jl
- Pinned ref: `v0.5.2`
- Resolved commit: `f688e70663ead21aef480bc74711bbf320d7825e`
- Source archive SHA-256: `a47576ea42c9ff38b6783c09706b7a9327760db3f9b43b5d5d9253aba4c28d85`
- SPDX license identifier: `MIT`
- Copyright holder: JosephsonCircuits.jl contributors
- Install mode: isolated Julia project
- Integration mode: Julia subprocess and JSON/netlist file exchange
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.solvers.josephsoncircuits`
- Dataset license: not_applicable
- Human review required: false

## scqubits

- Upstream: https://github.com/scqubits/scqubits
- Pinned ref: `v4.3.1`
- Resolved commit: `1dfb8b6ef3337d9fea5eb4bba21af8e36551adaa`
- Source archive SHA-256: `cdba2edc0f58b663bdbc1bf3c9b4d69f12951ba3d4acfd8478f5c90c095ad922`
- SPDX license identifier: `BSD-3-Clause`
- Copyright holder: scqubits contributors
- Install mode: uv optional dependency group quantum
- Integration mode: Python package adapter
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.solvers.scqubits_adapter`
- Dataset license: not_applicable
- Human review required: false

## pyEPR

- Upstream: https://github.com/zlatko-minev/pyEPR
- Pinned ref: `1.0.0`
- Resolved commit: `39a85e5501421d57f869ae3d7337a2c20da830f3`
- Source archive SHA-256: `8ea231e715dd560993396769c2227eb86359619272590f950af3d2e54fad7a13`
- SPDX license identifier: `NOASSERTION`
- Copyright holder: pyEPR contributors
- Install mode: unsupported historical reference; no install path in supported dependency groups or OCI images
- Integration mode: disabled commercial-HFSS path; retained only for attribution and imported field-energy compatibility notes
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.epr`
- Dataset license: not_applicable
- Human review required: true

## openEMS

- Upstream: https://github.com/thliebig/openEMS
- Pinned ref: `v0.0.36`
- Resolved commit: `5f36e7f3a2367123f00999491a069aed50c6f244`
- Source archive SHA-256: `57389b04fc0613d266b2d8d73d87ecb8a5405ad124081f6e5b73987c6253f473`
- SPDX license identifier: `GPL-3.0-or-later`
- Copyright holder: openEMS contributors
- Install mode: isolated OCI image or external executable
- Integration mode: external GPL FDTD runtime via subprocess and process-isolated file exchange
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout._legacy.solvers.openems`
- Dataset license: not_applicable
- Human review required: false

## JoSIM

- Upstream: https://github.com/JoeyDelp/JoSIM
- Pinned ref: `v2.7`
- Resolved commit: `02a34ee5e7a3a6952b21ccc726fbf7a6d5e2b224`
- Source archive SHA-256: `900d763011bcaba3413d18d159514aab74ec69d319346bc8ca646dc75fc6e4eb`
- SPDX license identifier: `GPL-3.0-or-later`
- Copyright holder: JoSIM contributors
- Install mode: isolated OCI image or external executable
- Integration mode: external GPL transient runtime via subprocess and process-isolated file exchange
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout._legacy.simulation.backends.josim`
- Dataset license: not_applicable
- Human review required: false

## SQuADDS

- Upstream: https://github.com/LFL-Lab/SQuADDS
- Pinned ref: `v0.4.5`
- Resolved commit: `beace3e52ceb491b8ef85b7e3f5439cb8273f248`
- Source archive SHA-256: `f4e1d195b3edbfcd34826694ffa5bd99233f381cf87a5899304b54590ce88df2`
- SPDX license identifier: `MIT`
- Copyright holder: SQuADDS contributors
- Install mode: separate environment and optional MCP server
- Integration mode: MCP process returning priors and dataset metadata only
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.external.squadds_mcp`
- Dataset license: recorded_by_dataset_metadata
- Human review required: false

## Quantum Metal / Qiskit Metal

- Upstream: https://github.com/qiskit-community/qiskit-metal
- Pinned ref: `v0.7.5`
- Resolved commit: `3ec90a580ab05c2c1b94ef934942f742daf1d8ab`
- Source archive SHA-256: `3b6b1399b6bcdaee32ec5bd7b2f687aa82534dec1eaef04fcba3226526c9da1f`
- SPDX license identifier: `Apache-2.0`
- Copyright holder: Qiskit Metal contributors
- Install mode: uv optional dependency group metal
- Integration mode: optional Python interoperability adapter
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.external.quantum_metal`
- Dataset license: not_applicable
- Human review required: false

## SQDMetal

- Upstream: https://github.com/sqdlab/SQDMetal
- Pinned ref: `c0026ea6ee5b932dbdcd20843bc70e130f705d69`
- Resolved commit: `c0026ea6ee5b932dbdcd20843bc70e130f705d69`
- Source archive SHA-256: `8cbd054f73ddfcd2422ca55f1b90efcb504a6ad84a15d4895e3e2de160a31e01`
- SPDX license identifier: `Apache-2.0`
- Copyright holder: SQDMetal contributors
- Install mode: separate Python environment
- Integration mode: file-exchange reference workflow adapter
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.external.sqdmetal`
- Dataset license: not_applicable
- Human review required: false

## KQCircuits

- Upstream: https://github.com/iqm-finland/KQCircuits
- Pinned ref: `v4.9.12`
- Resolved commit: `71cad094a65da90d65b7b9f8c5ed0e6c6f079d18`
- Source archive SHA-256: `af6cf100b61cc1149d62ac3742ae57f1c0b6213af3a9cf616f24fef33b76716f`
- SPDX license identifier: `GPL-3.0`
- Copyright holder: IQM Finland Oy and KQCircuits contributors
- Install mode: separate KLayout environment
- Integration mode: process-isolated GDS, JSON, runset, and result file exchange
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.external.kqcircuits_bridge`
- Dataset license: not_applicable
- Human review required: false

## KLayout

- Upstream: https://github.com/KLayout/klayout
- Pinned ref: `v0.30.9`
- Resolved commit: `6270877110ef808dd442fd2244164cec06a7b10e`
- Source archive SHA-256: `2d0582a893a1dbae50ed238b57b0ee76f3e4143f07b83b438d14cd612000bd63`
- SPDX license identifier: `GPL-3.0`
- Copyright holder: KLayout contributors
- Install mode: external executable or PyPI wheel, not vendored source
- Integration mode: process-isolated DRC/LVS runsets and report file exchange
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `textlayout.verification.klayout`
- Dataset license: not_applicable
- Human review required: false

## spdx-tools

- Upstream: https://github.com/spdx/tools-python
- Pinned ref: `v0.8.3`
- Resolved commit: `spdx-tools-0.8.3`
- Source archive SHA-256: `68b8f9ce2893b5216bd90b2e63f1c821c2884e4ebc4fd295ebbf1fa8b8a94b93`
- SPDX license identifier: `Apache-2.0`
- Copyright holder: SPDX tools-python contributors
- Install mode: uvx ephemeral pinned Python package
- Integration mode: external CLI validates generated SPDX JSON documents
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `scripts.validate_spdx_sbom`
- Dataset license: not_applicable
- Human review required: false

## Syft

- Upstream: https://github.com/anchore/syft
- Pinned ref: `v1.46.0`
- Resolved commit: `b15c5dbfe2bb21c9d73002c1056a829c8c411c75`
- Source archive SHA-256: `8bbbb3a27cca304c70192923834faa4c025b75a5ddbc9303ec5eed6e486e224a`
- SPDX license identifier: `Apache-2.0`
- Copyright holder: Anchore, Inc. and Syft contributors
- Install mode: pinned OCI image
- Integration mode: external container generates release SPDX JSON SBOMs
- Redistributes source: false
- Redistributes binaries: false
- Adapter module: `scripts.generate_syft_sbom`
- Dataset license: not_applicable
- Human review required: false
