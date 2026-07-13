# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG OPENEMS_COMMIT=5f36e7f3a2367123f00999491a069aed50c6f244
ARG OPENEMS_SHA256=57389b04fc0613d266b2d8d73d87ecb8a5405ad124081f6e5b73987c6253f473

LABEL org.opencontainers.image.title="Textlayout openEMS boundary" \
      org.opencontainers.image.description="Pinned openEMS identity boundary; full FDTD runs outside image build" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${OPENEMS_COMMIT}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /opt/textlayout /solver-output \
    && printf '{"tool":"openEMS","commit":"%s","source_archive_sha256":"%s","status":"identity_recorded_not_solver_executed"}\n' "${OPENEMS_COMMIT}" "${OPENEMS_SHA256}" > /opt/textlayout/tool-identity.json \
    && printf '{"SPDXID":"SPDXRef-DOCUMENT","spdxVersion":"SPDX-2.3","name":"textlayout-openems","packages":[{"SPDXID":"SPDXRef-Package-openems","name":"openEMS","versionInfo":"%s","licenseConcluded":"GPL-3.0-or-later"}]}\n' "${OPENEMS_COMMIT}" > /opt/textlayout/sbom.spdx.json \
    && chown -R appuser:appuser /solver-output /opt/textlayout

USER appuser
VOLUME ["/solver-output"]
CMD ["sh", "-lc", "cat /opt/textlayout/tool-identity.json"]
