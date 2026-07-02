# Simulator licenses and redistribution rules

This project never vendors simulator source or binaries into the repository;
everything lands in the git-ignored `.tools/` directory on the user's
machine. What the bootstrap is allowed to do differs per tool:

| Tool | License | What our scripts do | Why |
| --- | --- | --- | --- |
| JoSIM | MIT (github.com/JoeyDelp/JoSIM) | Download official release artifacts and/or build from source automatically | MIT explicitly permits use and redistribution; we still fetch only from the official release channel |
| PSCAN2 | See http://pscan2sim.org/ | Detect only; print official install instructions | No scriptable, license-clear distribution path is documented for automation |
| WRspice (XicTools) | GPL-3.0 source (github.com/wrcad/xictools); binaries distributed by Whiteley Research at wrcad.com | Detect only; never download or mirror binaries | We do not assume redistribution/mirroring rights over wrcad.com binary packages; users install from the official site |
| FasterCap / FastCap2 | FastFieldSolvers distribution terms (fastfieldsolvers.com) | Detect only | Same conservatism: official channel, user-driven install |

Additional rules encoded in the tooling:

- `.tools/` is git-ignored; CI and Docker builds re-fetch rather than commit.
- No third-party build trees or caches under `src/` — scratch space is
  `.tools/build/`.
- The reference repository `external_references/JTWPA_Numerical_Simulations`
  has **no license file** (all rights reserved by default): it is cloned
  locally for study only, never redistributed, and nothing from it is copied
  into generated decks. Citation: doi 10.1109/TASC.2024.3364125.
- Docker images built from `docker/simulators.Dockerfile` contain a JoSIM
  binary obtained from the official MIT-licensed releases; do not add
  WRspice/PSCAN2 layers to published images without checking their terms.
