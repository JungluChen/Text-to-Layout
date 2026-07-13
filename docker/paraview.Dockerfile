# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG PARAVIEW_VERSION=v5.13.3
ARG PARAVIEW_COMMIT=33274c1e71474b91721a41e3c449277d1e67d1ae
ARG PARAVIEW_SHA256=9089d61f5928cd20ff90218b6e77a02f08690ca75518cab96f455dc86fc7a719

LABEL org.opencontainers.image.title="Textlayout ParaView boundary" \
      org.opencontainers.image.description="Pinned ParaView identity boundary for visualization workflows" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${PARAVIEW_VERSION}" \
      org.opencontainers.image.licenses="BSD-3-Clause"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /opt/textlayout /solver-output \
    && printf '{"tool":"ParaView","version":"%s","commit":"%s","source_archive_sha256":"%s","status":"identity_recorded_not_solver_executed"}\n' "${PARAVIEW_VERSION}" "${PARAVIEW_COMMIT}" "${PARAVIEW_SHA256}" > /opt/textlayout/tool-identity.json \
    && printf '{"SPDXID":"SPDXRef-DOCUMENT","spdxVersion":"SPDX-2.3","name":"textlayout-paraview","packages":[{"SPDXID":"SPDXRef-Package-paraview","name":"ParaView","versionInfo":"%s","licenseConcluded":"BSD-3-Clause"}]}\n' "${PARAVIEW_VERSION}" > /opt/textlayout/sbom.spdx.json \
    && chown -R appuser:appuser /solver-output /opt/textlayout

USER appuser
VOLUME ["/solver-output"]
CMD ["sh", "-lc", "cat /opt/textlayout/tool-identity.json"]
