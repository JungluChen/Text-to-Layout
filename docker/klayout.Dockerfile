# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG KLAYOUT_VERSION=0.30.9
ARG KLAYOUT_COMMIT=6270877110ef808dd442fd2244164cec06a7b10e
ARG KLAYOUT_SHA256=2d0582a893a1dbae50ed238b57b0ee76f3e4143f07b83b438d14cd612000bd63
ARG KLAYOUT_DEB_URL=https://www.klayout.org/downloads/Ubuntu-24/klayout_0.30.9-1_amd64.deb
ARG KLAYOUT_DEB_SHA256=a5e50f194edc6893caa26b0b76764a9c2b3ab4a9f8fa5a9ca0fe471381d702eb

LABEL org.opencontainers.image.title="Textlayout KLayout boundary" \
      org.opencontainers.image.description="Pinned KLayout runtime for headless DRC/LVS smoke" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${KLAYOUT_VERSION}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl python3 tini; \
    curl -fsSL "${KLAYOUT_DEB_URL}" -o /tmp/klayout.deb; \
    echo "${KLAYOUT_DEB_SHA256}  /tmp/klayout.deb" | sha256sum -c -; \
    apt-get install -y --no-install-recommends /tmp/klayout.deb; \
    rm -f /tmp/klayout.deb; \
    rm -rf /var/lib/apt/lists/*; \
    useradd --create-home --uid 10001 appuser; \
    mkdir -p /opt/textlayout /solver-output; \
    command -v klayout; \
    klayout -b -v; \
    KLAYOUT_BIN="$(command -v klayout)"; \
    KLAYOUT_BIN_SHA256="$(sha256sum "$KLAYOUT_BIN" | awk '{print $1}')"; \
    export KLAYOUT_BIN KLAYOUT_BIN_SHA256 KLAYOUT_VERSION KLAYOUT_COMMIT KLAYOUT_SHA256 KLAYOUT_DEB_URL KLAYOUT_DEB_SHA256 SOURCE_REVISION; \
    python3 -c 'import json, os, pathlib, subprocess; payload={"tool":"KLayout","version":os.environ["KLAYOUT_VERSION"],"upstream_commit":os.environ["KLAYOUT_COMMIT"],"source_archive_sha256":os.environ["KLAYOUT_SHA256"],"deb_url":os.environ["KLAYOUT_DEB_URL"],"deb_sha256":os.environ["KLAYOUT_DEB_SHA256"],"source_revision":os.environ["SOURCE_REVISION"],"executable":os.environ["KLAYOUT_BIN"],"executable_sha256":os.environ["KLAYOUT_BIN_SHA256"],"identity_command":["klayout","-b","-v"],"identity_stdout":subprocess.check_output(["klayout","-b","-v"], text=True).strip(),"status":"IDENTITY_VERIFIED"}; pathlib.Path("/opt/textlayout/tool-identity.json").write_text(json.dumps(payload, indent=2)+"\n", encoding="utf-8")'; \
    printf '{"SPDXID":"SPDXRef-DOCUMENT","spdxVersion":"SPDX-2.3","name":"textlayout-klayout-placeholder","comment":"Real image SBOM is generated after image build with docker sbom/Syft and stored as an audit artifact; this file is not a complete SBOM."}\n' > /opt/textlayout/sbom.spdx.json; \
    chown -R appuser:appuser /solver-output /opt/textlayout

USER appuser
VOLUME ["/solver-output"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-lc", "klayout -b -v && cat /opt/textlayout/tool-identity.json"]
