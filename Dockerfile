# syntax=docker/dockerfile:1.7
# Multi-stage Dockerfile for Text-to-Layout reproducible runtime & solver toolchain

# ==============================================================================
# Stage 1: Builder (Pinned builds of Palace, Gmsh, FasterCap, FastHenry2, JoSIM, openEMS)
# ==============================================================================
# The prebuilt Gmsh 4.15.2 binary and the PyPI `gmsh` wheel are linux/amd64
# only, and the native solver stack is built/tested for x86_64. Pinning the
# platform keeps a plain `docker build` working on Apple Silicon (via Docker
# Desktop emulation) instead of failing halfway through `uv sync`.
FROM --platform=linux/amd64 ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

# WITH_SOLVERS=1 (default) builds every native solver and FAILS the image if one
# cannot be produced. Set to 0 only for a geometry/doctor-only image; the
# resulting image is then honestly labelled solvers=absent instead of silently
# shipping an incomplete toolchain.
ARG WITH_SOLVERS=1
ARG PALACE_VERSION=0.17.0
ARG PALACE_COMMIT=12d8069afb5aa9e169a17e303d735e120968e9f2
ARG OPENEMS_COMMIT=5f36e7f3a2367123f00999491a069aed50c6f244
# Optional exact commit pins for the FastFieldSolvers repositories. Empty means
# "track the default branch"; the resolved SHA is still recorded in install.json.
ARG FASTHENRY_COMMIT=""
ARG FASTERCAP_COMMIT=""

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    ca-certificates \
    pkg-config \
    gfortran \
    libopenmpi-dev \
    openmpi-bin \
    libboost-all-dev \
    libfftw3-dev \
    libhdf5-dev \
    libtinyxml-dev \
    libxml2-dev \
    libglu1-mesa-dev \
    libxrender-dev \
    libxcursor-dev \
    libxft-dev \
    libxinerama-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN mkdir -p /opt/textlayout-tools/palace/bin \
    /opt/textlayout-tools/gmsh/bin \
    /opt/textlayout-tools/fastercap/bin \
    /opt/textlayout-tools/fasthenry2/bin \
    /opt/textlayout-tools/josim/bin \
    /opt/textlayout-tools/openEMS/bin \
    /opt/textlayout-tools/openEMS/share/openEMS/matlab \
    /opt/textlayout-tools/openEMS/share/CSXCAD/matlab

# Each solver block is guarded by WITH_SOLVERS and uses `set -eu` so a failed
# build fails the image instead of leaving an empty bin/ directory behind.
# 1. FastHenry2 (PEEC solver)
RUN set -eu; \
    if [ "$WITH_SOLVERS" = "1" ]; then \
      git clone https://github.com/FastFieldSolvers/FastHenry2.git /tmp/fasthenry; \
      cd /tmp/fasthenry; \
      if [ -n "$FASTHENRY_COMMIT" ]; then git checkout "$FASTHENRY_COMMIT"; fi; \
      git rev-parse HEAD > /tmp/fasthenry.commit; \
      cd src/fasthenry; \
      make all default; \
      cp -f ../../bin/fasthenry /opt/textlayout-tools/fasthenry2/bin/fasthenry; \
      rm -rf /tmp/fasthenry; \
    fi

# 2. JoSIM 2.7 (Superconducting circuit simulator)
RUN set -eu; \
    if [ "$WITH_SOLVERS" = "1" ]; then \
      git clone --depth 1 --branch v2.7 https://github.com/JoeyDelp/JoSIM.git /tmp/josim; \
      cd /tmp/josim; \
      git rev-parse HEAD > /tmp/josim.commit; \
      mkdir build; cd build; \
      cmake -DCMAKE_BUILD_TYPE=Release ..; \
      cmake --build . -j"$(nproc)"; \
      cp -f josim /opt/textlayout-tools/josim/bin/josim; \
      rm -rf /tmp/josim; \
    fi

# 3. FasterCap (BEM capacitance solver)
RUN set -eu; \
    if [ "$WITH_SOLVERS" = "1" ]; then \
      git clone https://github.com/FastFieldSolvers/FasterCap.git /tmp/fastercap; \
      cd /tmp/fastercap; \
      if [ -n "$FASTERCAP_COMMIT" ]; then git checkout "$FASTERCAP_COMMIT"; fi; \
      git rev-parse HEAD > /tmp/fastercap.commit; \
      mkdir -p build; cd build; \
      cmake -DCMAKE_BUILD_TYPE=Release ..; \
      cmake --build . -j"$(nproc)"; \
      cp -f FasterCap /opt/textlayout-tools/fastercap/bin/FasterCap; \
      rm -rf /tmp/fastercap; \
    fi

# 4. Gmsh 4.15.2 (Finite Element Mesh Generator) — checksum from the vendor
RUN set -eu; \
    if [ "$WITH_SOLVERS" = "1" ]; then \
      curl -fsSL https://gmsh.info/bin/Linux/gmsh-4.15.2-Linux64.tgz -o /tmp/gmsh.tgz; \
      curl -fsSL https://gmsh.info/bin/Linux/gmsh-4.15.2-Linux64.tgz.sha256 -o /tmp/gmsh.sha256; \
      cd /tmp; sha256sum -c gmsh.sha256; \
      tar -xzf /tmp/gmsh.tgz -C /tmp; \
      cp -f /tmp/gmsh-4.15.2-Linux64/bin/gmsh /opt/textlayout-tools/gmsh/bin/gmsh; \
      rm -rf /tmp/gmsh*; \
    fi

# 5. openEMS & CSXCAD (FDTD EM solver) — exact commit, verified after checkout
RUN set -eu; \
    if [ "$WITH_SOLVERS" = "1" ]; then \
      git clone --recursive https://github.com/thliebig/openEMS-Project.git /tmp/openEMS-Project; \
      cd /tmp/openEMS-Project; \
      git checkout "$OPENEMS_COMMIT"; \
      test "$(git rev-parse HEAD)" = "$OPENEMS_COMMIT"; \
      ./update_openEMS.sh /opt/textlayout-tools/openEMS --disable-hyp2mat; \
      rm -rf /tmp/openEMS-Project; \
    fi

# 6. Palace 0.17.0 (3D FEM Eigenmode and Driven solver)
# The tag must resolve to PALACE_COMMIT; otherwise the build aborts rather than
# shipping a binary with unverified provenance.
RUN set -eu; \
    if [ "$WITH_SOLVERS" = "1" ]; then \
      git clone --depth 1 --branch "v${PALACE_VERSION}" https://github.com/awslabs/palace.git /tmp/palace; \
      cd /tmp/palace; \
      git fetch --depth 1 origin "$PALACE_COMMIT"; \
      git checkout "$PALACE_COMMIT"; \
      test "$(git rev-parse HEAD)" = "$PALACE_COMMIT"; \
      git rev-parse HEAD > /tmp/palace.commit; \
      mkdir build; cd build; \
      cmake -DCMAKE_BUILD_TYPE=Release -DPALACE_WITH_OPENMP=ON ..; \
      cmake --build . -j"$(nproc)"; \
      cp -f bin/palace /opt/textlayout-tools/palace/bin/palace; \
      rm -rf /tmp/palace; \
    fi

# Fail the build if any requested solver is missing or not executable.
RUN set -eu; \
    if [ "$WITH_SOLVERS" = "1" ]; then \
      for binary in \
        /opt/textlayout-tools/palace/bin/palace \
        /opt/textlayout-tools/gmsh/bin/gmsh \
        /opt/textlayout-tools/fastercap/bin/FasterCap \
        /opt/textlayout-tools/fasthenry2/bin/fasthenry \
        /opt/textlayout-tools/josim/bin/josim \
        /opt/textlayout-tools/openEMS/bin/openEMS; do \
        test -x "$binary" || { echo "missing solver binary: $binary" >&2; exit 1; }; \
      done; \
    fi

# Traceable provenance for the built image (commits resolved at build time).
RUN set -eu; \
    { \
      printf '{\n  "schema": "textlayout.container-install.v1",\n'; \
      printf '  "with_solvers": %s,\n' "$WITH_SOLVERS"; \
      printf '  "palace_version": "%s",\n' "$PALACE_VERSION"; \
      printf '  "palace_commit": "%s",\n' "$(cat /tmp/palace.commit 2>/dev/null || echo '')"; \
      printf '  "openems_commit": "%s",\n' "$OPENEMS_COMMIT"; \
      printf '  "fasthenry_commit": "%s",\n' "$(cat /tmp/fasthenry.commit 2>/dev/null || echo '')"; \
      printf '  "fastercap_commit": "%s"\n' "$(cat /tmp/fastercap.commit 2>/dev/null || echo '')"; \
      printf '}\n'; \
    } > /opt/textlayout-tools/install.json; \
    chmod -R a+rx /opt/textlayout-tools

# ==============================================================================
# Stage 2: Runtime (Minimal runtime libraries, headless KLayout, Python 3.12, uv)
# ==============================================================================
FROM --platform=linux/amd64 ubuntu:24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    UV_PROJECT_ENVIRONMENT=/opt/textlayout-venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/palace/bin:/opt/gmsh/bin:/opt/fastercap/bin:/opt/fasthenry2/bin:/opt/josim/bin:/opt/openEMS/bin:/opt/textlayout-venv/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/palace/lib:/opt/openEMS/lib:/opt/openEMS/lib64" \
    TEXTLAYOUT_PALACE="/opt/palace/bin/palace" \
    TEXTLAYOUT_GMSH="/opt/gmsh/bin/gmsh" \
    TEXTLAYOUT_FASTERCAP="/opt/fastercap/bin/FasterCap" \
    TEXTLAYOUT_FASTHENRY="/opt/fasthenry2/bin/fasthenry" \
    TEXTLAYOUT_JOSIM="/opt/josim/bin/josim" \
    TEXTLAYOUT_OPENEMS_CORE="/opt/openEMS/bin/openEMS" \
    MPLBACKEND=Agg \
    QISKIT_METAL_HEADLESS=1 \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2

# Install minimal runtime dependencies and headless KLayout
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3-pip \
    curl \
    ca-certificates \
    tini \
    openmpi-bin \
    libopenmpi3t64 \
    octave \
    octave-control \
    octave-signal \
    libglu1-mesa \
    libxrender1 \
    libxcursor1 \
    libxft2 \
    libxinerama1 \
    libfontconfig1 \
    klayout \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /bin/

# Copy compiled/staged EDA tools from builder
COPY --from=builder /opt/textlayout-tools/ /opt/

WORKDIR /workspace

# Pre-cache project dependencies using uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --all-extras --no-install-project

# Copy source tree and install project
COPY . .
RUN uv sync --frozen --all-extras

# Configure Octave paths for openEMS (system-wide and per-user)
RUN printf "addpath('/opt/openEMS/share/openEMS/matlab');\naddpath('/opt/openEMS/share/CSXCAD/matlab');\n" > /etc/octaverc \
    && cp /etc/octaverc /root/.octaverc

# Add non-root user for secure container execution
RUN useradd --create-home --uid 10001 appuser \
    && cp /etc/octaverc /home/appuser/.octaverc \
    && chown -R appuser:appuser /workspace /opt/textlayout-venv /opt /home/appuser

EXPOSE 8000

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uv", "run", "textlayout", "serve", "--host", "0.0.0.0", "--port", "8000"]
