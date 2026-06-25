# External Backend Integration Status

Generated status should be refreshed with:

```bash
uv run python scripts/check_external_tools.py
```

Optional repository bootstrap:

```bash
uv run python scripts/bootstrap_external_repos.py --clone
```

## Status Vocabulary

| Status | Meaning | Counts as solver evidence |
|---|---|---|
| `executed` | Solver ran and produced an output file. | Yes |
| `installed` | Python module or package is available. | No |
| `binary_found` | Executable was detected. | No |
| `input_files_prepared` | Solver handoff files exist. | No |
| `skipped` | Solver not available or not run. | No |
| `planned` | Integration target only. | No |

## External Repositories (`.tools/repos/`)

| Repo | URL | Role |
|---|---|---|
| KQCircuits | https://github.com/iqm-finland/KQCircuits | Superconducting layout backend |
| gdsfactory | https://github.com/gdsfactory/gdsfactory | Layout glue, booleans, GDS export |
| qiskit-metal | https://github.com/Qiskit/qiskit-metal | Qubit and CPW layout backend |
| JosephsonCircuits.jl | https://github.com/kpobrien/JosephsonCircuits.jl | JPA/JTWPA nonlinear circuit solver |
| JoSIM | https://github.com/JoeyDelp/JoSIM | SFQ transient solver |
| scqubits | https://github.com/scqubits/scqubits | Hamiltonian spectrum solver |
| pyEPR | https://github.com/zlatko-minev/pyEPR | Energy participation analysis |
| openEMS | https://github.com/thliebig/openEMS | FDTD EM solver |
| Palace | https://github.com/awslabs/palace | FEM eigenmode solver |
| Elmer FEM | https://github.com/ElmerCSC/elmerfem | FEM electrostatic extraction |
| FastCap2 | https://github.com/ediloren/FastCap2 | Capacitance extraction |
| FastHenry2 | https://github.com/ediloren/FastHenry2 | Inductance extraction |

## Manual Install Steps

- Julia: install Julia, then run `uv run python scripts/setup_external_tools.py`.
- JosephsonCircuits.jl: use `scripts/install_julia_packages.jl`.
- JoSIM: install JoSIM or place `josim.exe` under `.tools/josim-*/bin/`.
- openEMS: install openEMS and Octave or place `openEMS.exe` under
  `.tools/openEMS-*/openEMS/`.
- Palace: build with CMake and MPI, then place `palace.exe` on PATH.
- Elmer FEM: install Elmer and put `ElmerSolver` on PATH.
- FastCap2/FastHenry2: build and place executables on PATH or under `.tools/`.
- Qiskit Metal: use a Python 3.10/Qt-compatible environment when Windows
  Python 3.12 cannot install PySide2.

## Benchmark Asset Rules

Each benchmark has two image outputs:

- `*_layout.png`: geometry only.
- `*_benchmark.png`: geometry plus extraction and solver evidence or skipped
  status.

Do not overwrite layout images with status panels. Do not write `SOLVER
EXECUTED` unless a solver-owned output file exists.
