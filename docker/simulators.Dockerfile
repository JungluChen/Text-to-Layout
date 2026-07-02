# Reproducible simulator environment for Text-to-Layout.
#
#   docker build -f docker/simulators.Dockerfile -t textlayout-simulators .
#   docker run --rm textlayout-simulators make check-simulators
#   docker run --rm textlayout-simulators make demo-jpa
#
# Honesty policy: the build installs JoSIM (primary backend) via the official
# release artifact or a source build; PSCAN2 and WRspice remain
# manual_install_required and that is what the final table says. Nothing is
# ever reported as available unless the executable actually runs, and an
# installed simulator still does not mean PHYSICS_VERIFIED.

FROM python:3.12-slim

# Build tools for the JoSIM source-build fallback (and native wheels).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ninja-build curl ca-certificates make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Project dependencies first (better layer caching), then the source tree.
COPY pyproject.toml uv.lock* README.md ./
RUN pip install --no-cache-dir uv && (uv sync --frozen || uv sync)

COPY . .
RUN uv sync

# [1/3] Bootstrap simulators: installs JoSIM (release artifact, else source
# build); PSCAN2/WRspice are detected and honestly left manual. A failed
# JoSIM install prints diagnostics but does not silently pass: the strict
# check below is the gate.
RUN python scripts/bootstrap_simulators.py

# [2/3] Gate the image on the primary backend being genuinely runnable.
# This is intentionally strict inside Docker - a "simulators" image without
# JoSIM would be a lie. Failures fail the build loudly.
RUN python scripts/check_simulators.py --strict --require josim

# [3/3] Run the JPA demo with the real JoSIM now present. The demo's own
# report stays honest: capacitance extraction is still FasterCap territory
# and will be reported as absent unless that solver is also installed.
RUN uv run textlayout prompt "Design a lumped-element JPA for 2.3 GHz with 50 MHz bandwidth, 13 dB gain target, using an IDC capacitor and SQUID-equivalent inductance. Generate layout, verify it, extract capacitance if possible, and prepare JoSIM, PSCAN2, and WRspice simulations." --out out/jpa_demo

# Final availability table baked into the build log.
RUN python scripts/check_simulators.py

CMD ["python", "scripts/check_simulators.py"]
