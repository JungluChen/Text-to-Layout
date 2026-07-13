# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG JOSIM_VERSION=v2.7
ARG JOSIM_COMMIT=02a34ee5e7a3a6952b21ccc726fbf7a6d5e2b224
ARG JOSIM_SHA256=900d763011bcaba3413d18d159514aab74ec69d319346bc8ca646dc75fc6e4eb

LABEL org.opencontainers.image.title="Textlayout JoSIM boundary" \
      org.opencontainers.image.description="Pinned JoSIM identity boundary for transient workflows" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${JOSIM_VERSION}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /opt/textlayout /solver-output \
    && printf '{"tool":"JoSIM","version":"%s","commit":"%s","source_archive_sha256":"%s","status":"identity_recorded_not_solver_executed"}\n' "${JOSIM_VERSION}" "${JOSIM_COMMIT}" "${JOSIM_SHA256}" > /opt/textlayout/tool-identity.json \
    && printf '{"SPDXID":"SPDXRef-DOCUMENT","spdxVersion":"SPDX-2.3","name":"textlayout-josim","packages":[{"SPDXID":"SPDXRef-Package-josim","name":"JoSIM","versionInfo":"%s","licenseConcluded":"GPL-3.0-or-later"}]}\n' "${JOSIM_VERSION}" > /opt/textlayout/sbom.spdx.json \
    && chown -R appuser:appuser /solver-output /opt/textlayout

USER appuser
VOLUME ["/solver-output"]
CMD ["sh", "-lc", "cat /opt/textlayout/tool-identity.json"]
