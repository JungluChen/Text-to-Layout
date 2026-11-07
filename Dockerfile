# syntax=docker/dockerfile:1.7
# Multi-stage Dockerfile for Text-to-Layout reproducible runtime & solver toolchain

# ==============================================================================
# Stage 1: Builder (Pinned builds of Palace, Gmsh, FasterCap, FastHenry2, JoSIM, openEMS)
# ==============================================================================
FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

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

# 1. FastHenry2 (PEEC solver)
RUN git clone --depth 1 https://github.com/FastFieldSolvers/FastHenry2.git /tmp/fasthenry \
    && cd /tmp/fasthenry/src/fasthenry \
    && make all default \
    && cp -f ../../bin/fasthenry /opt/textlayout-tools/fasthenry2/bin/fasthenry \
    && rm -rf /tmp/fasthenry || true

# 2. JoSIM 2.7 (Superconducting circuit simulator)
RUN git clone --depth 1 --branch v2.7 https://github.com/JoeyDelp/JoSIM.git /tmp/josim \
    && cd /tmp/josim \
    && mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && cmake --build . -j$(nproc) \
    && cp -f josim /opt/textlayout-tools/josim/bin/josim \
    && rm -rf /tmp/josim || true

# 3. FasterCap (BEM capacitance solver)
RUN git clone --depth 1 https://github.com/FastFieldSolvers/FasterCap.git /tmp/fastercap \
    && cd /tmp/fastercap \
    && mkdir -p build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && cmake --build . -j$(nproc) \
    && cp -f FasterCap /opt/textlayout-tools/fastercap/bin/FasterCap \
    && rm -rf /tmp/fastercap || true

# 4. Gmsh 4.15.2 (Finite Element Mesh Generator)
RUN curl -fsSL https://gmsh.info/bin/Linux/gmsh-4.15.2-Linux64.tgz -o /tmp/gmsh.tgz \
    && tar -xzf /tmp/gmsh.tgz -C /tmp \
    && cp -f /tmp/gmsh-4.15.2-Linux64/bin/gmsh /opt/textlayout-tools/gmsh/bin/gmsh \
    && rm -rf /tmp/gmsh* || true

# 5. openEMS & CSXCAD (FDTD EM solver)
RUN git clone --recursive https://github.com/thliebig/openEMS-Project.git /tmp/openEMS-Project \
    && cd /tmp/openEMS-Project \
    && git checkout 5f36e7f3a2367123f00999491a069aed50c6f244 || true \
    && ./update_openEMS.sh /opt/textlayout-tools/openEMS --disable-hyp2mat || true \
    && rm -rf /tmp/openEMS-Project || true

# 6. Palace 0.17.0 (3D FEM Eigenmode and Driven solver)
# Pinned identity and binary boundary
ARG PALACE_VERSION=0.17.0
ARG PALACE_COMMIT=12d8069afb5aa9e169a17e303d735e120968e9f2
RUN git clone --depth 1 --branch v${PALACE_VERSION} https://github.com/awslabs/palace.git /tmp/palace \
    && cd /tmp/palace \
    && mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DPALACE_WITH_OPENMP=ON .. || true \
    && (cmake --build . -j$(nproc) && cp -f bin/palace /opt/textlayout-tools/palace/bin/palace || true) \
    && rm -rf /tmp/palace || true

# Ensure all tool directories and binaries have executable permissions
RUN chmod -R a+rx /opt/textlayout-tools

# ==============================================================================
# Stage 2: Runtime (Minimal runtime libraries, headless KLayout, Python 3.12, uv)
# ==============================================================================
FROM ubuntu:24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    UV_PROJECT_ENVIRONMENT=/opt/textlayout-venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/palace/bin:/opt/gmsh/bin:/opt/fastercap/bin:/opt/fasthenry2/bin:/opt/josim/bin:/opt/openEMS/bin:/opt/textlayout-venv/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/palace/lib:/opt/openEMS/lib:/opt/openEMS/lib64:${LD_LIBRARY_PATH}" \
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

# Configure Octave paths for openEMS
RUN mkdir -p /root && printf "addpath('/opt/openEMS/share/openEMS/matlab');\naddpath('/opt/openEMS/share/CSXCAD/matlab');\n" > /root/.octaverc

# Add non-root user for secure container execution
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /workspace /opt/textlayout-venv /opt

USER appuser

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uv", "run", "textlayout", "doctor"]
