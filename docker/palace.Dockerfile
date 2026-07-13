# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG PALACE_VERSION=0.17.0
ARG PALACE_COMMIT=12d8069afb5aa9e169a17e303d735e120968e9f2
ARG PALACE_SHA256=169f7fe210ea6e771a29bfe0803dd84a774b25b00d2aa3a1f33b9d97a510ff9d

LABEL org.opencontainers.image.title="Textlayout Palace boundary" \
      org.opencontainers.image.description="Pinned Palace identity boundary; full solve runs outside image build" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${PALACE_VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /opt/textlayout /solver-output \
    && printf '{"tool":"Palace","version":"%s","commit":"%s","source_archive_sha256":"%s","status":"identity_recorded_not_solver_executed"}\n' "${PALACE_VERSION}" "${PALACE_COMMIT}" "${PALACE_SHA256}" > /opt/textlayout/tool-identity.json \
    && printf '{"SPDXID":"SPDXRef-DOCUMENT","spdxVersion":"SPDX-2.3","name":"textlayout-palace","packages":[{"SPDXID":"SPDXRef-Package-palace","name":"Palace","versionInfo":"%s","licenseConcluded":"Apache-2.0"}]}\n' "${PALACE_VERSION}" > /opt/textlayout/sbom.spdx.json \
    && chown -R appuser:appuser /solver-output /opt/textlayout

USER appuser
VOLUME ["/solver-output"]
CMD ["sh", "-lc", "cat /opt/textlayout/tool-identity.json"]
