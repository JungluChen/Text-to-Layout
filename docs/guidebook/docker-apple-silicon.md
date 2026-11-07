# Shared Docker environment on Apple Silicon

Document class: MANUAL_DOCUMENTATION.

The project owner's host is Apple Silicon. The research Compose environment
explicitly defaults to **linux/amd64** (x86-64 Linux), including build and run.
Mac Python environments and Mach-O binaries are never copied into the image.
The original host installation is preserved. Docker build/execution evidence
is pending until the real runtime and the commands below pass.

## Runtime and performance

Install Docker Desktop for **Apple Silicon**, not its Intel application.
Complete its first-run setup yourself, including applicable license terms.
In Docker Desktop settings, where available, select Apple Virtualization
Framework and enable Rosetta for x86_64/amd64 emulation. Docker VMM currently
does not support Rosetta; don't assume selecting it accelerates x86 workloads.
See [Docker settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/)
and [VMM guidance](https://docs.docker.com/desktop/features/vmm/).
No host emulation setting or performance claim can be inferred from a manifest.

Keep source/dependencies in the image and solver caches/output on Docker named
volumes to avoid Mac bind-mount overhead. Start with two numerical threads;
set TEXTLAYOUT_THREADS explicitly before benchmarking. Emulation is slower
than native x86 for some compilation and numerical workloads. For long solves,
use a native x86 Docker host with the same image digest. Native arm64 is an
optional separately tested build, not a silently interchangeable environment.

## Build and verify

From the repository root:

```sh
docker version
docker compose -f compose.research.yaml config
export SOURCE_REVISION=$(git rev-parse HEAD)
docker compose -f compose.research.yaml build --progress plain research
docker compose -f compose.research.yaml run --rm research uname -m
docker compose -f compose.research.yaml run --rm research textlayout doctor --json
docker compose -f compose.research.yaml run --rm research python scripts/check_python_packages.py --out out/imports-first
docker compose -f compose.research.yaml run --rm research python scripts/check_python_packages.py --out out/imports-repeat
docker compose -f compose.research.yaml run --rm research pytest
```

Expected architecture: x86_64. Both fresh-directory package reports must pass
all declared package imports, with no unmapped dependencies. The image build also repeats imports.
The image fixes the base digest, uv version, Debian snapshot and uv.lock;
installed OS/Python versions and source revision are in /opt/textlayout.
Record `docker image inspect textlayout/research:local-amd64` with test evidence.
A dirty source tree needs its diff retained as well as SOURCE_REVISION.
Do not mount a host .venv over /opt/textlayout-venv or /workspace.

CLI and API use this same environment:

```sh
docker compose -f compose.research.yaml run --rm research textlayout --help
docker compose -f compose.research.yaml run --rm --service-ports research textlayout serve --host 0.0.0.0 --port 8000
# Legacy MCP stdio, for a host that supports an external process:
docker compose -f compose.research.yaml run --rm -T research text-to-gds
```

API docs: http://127.0.0.1:8000/docs . The port is published only on loopback.
MCP host installation and schema discovery remain separate verification steps.
Use `run --rm research bash` for an interactive shell. Export persistent reports:

```sh
docker compose -f compose.research.yaml run --rm -T research tar -C /workspace/out -czf - . > container-output.tar.gz
```

The Python core, all declared extras, development tools, Octave, ngspice and
MPI prerequisites share one image. **Palace, openEMS, FasterCap, JoSIM and other
external targets are not declared installed by this image.** Existing pinned
installers must be executed and verified in this environment, with actual
smoke/repeat/convergence/reference evidence retained before scientific claims.
The old compose.yaml tool-identity images are not full solver installations.
No claim is made that 100 candidate tools can coexist or are all open source.

If Docker cannot connect, finish Docker Desktop startup and repeat `docker version`.
For exec-format errors inspect image architecture and Compose platform; rebuild
for linux/amd64. For import failures retain build logs and /opt/textlayout reports;
do not remove a package to make the gate pass. Output directories must be fresh.
`docker compose down` preserves named volumes; never use `down -v` unless their
contents have been exported and deletion is intended. Desktop settings screenshots
and measured Rosetta performance are pending; no screenshot is fabricated.

AI prompt: “Inspect my container architecture, package reports and doctor output;
separate installed packages from executed/validated solvers. Preserve failures.”

## Priority 1: retained official Palace smoke repeat

After the pinned Palace installer and installation check actually succeed in
Linux, run the official smoke in two fresh directories:

```sh
python scripts/external/check_palace.py
python scripts/external/run_palace_smoke.py --out out/toolchain/smoke-first
python scripts/external/run_palace_smoke.py --out out/toolchain/smoke-repeat
python scripts/external/check_palace_smoke_repeat.py --first out/toolchain/smoke-first --repeat out/toolchain/smoke-repeat --out out/toolchain/smoke-comparison.json
```

Existing explicit output directories are rejected, preserving earlier logs.
The comparison rehashes inputs/outputs, reparses eig.csv, checks binary identity
and matching mode indices/count, and requires each relative frequency drift
`abs(f_repeat-f_first)/f_first < 1e-6`. A repeatability pass is not mesh convergence
or physical validation. Actual official execution remains pending until retained
solver outputs exist. Synthetic regression fixtures test rejection paths only.
