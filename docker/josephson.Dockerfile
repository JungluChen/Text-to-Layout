# syntax=docker/dockerfile:1.7
FROM julia:1.10.10-bookworm@sha256:2323a3445e7701cf8f7190293e360e4f67c7e43de24480183f178aa1062dc99b

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG JOSEPHSONCIRCUITS_VERSION=v0.5.2
ARG JOSEPHSONCIRCUITS_COMMIT=f688e70663ead21aef480bc74711bbf320d7825e
ARG JOSEPHSONCIRCUITS_SHA256=a47576ea42c9ff38b6783c09706b7a9327760db3f9b43b5d5d9253aba4c28d85

LABEL org.opencontainers.image.title="Textlayout JosephsonCircuits boundary" \
      org.opencontainers.image.description="Pinned JosephsonCircuits.jl identity boundary for harmonic-balance workflows" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${JOSEPHSONCIRCUITS_VERSION}" \
      org.opencontainers.image.licenses="MIT"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /opt/textlayout /solver-output \
    && julia --version > /opt/textlayout/julia-version.txt \
    && printf '{"tool":"JosephsonCircuits.jl","version":"%s","commit":"%s","source_archive_sha256":"%s","status":"identity_recorded_not_solver_executed"}\n' "${JOSEPHSONCIRCUITS_VERSION}" "${JOSEPHSONCIRCUITS_COMMIT}" "${JOSEPHSONCIRCUITS_SHA256}" > /opt/textlayout/tool-identity.json \
    && printf '{"SPDXID":"SPDXRef-DOCUMENT","spdxVersion":"SPDX-2.3","name":"textlayout-josephson","packages":[{"SPDXID":"SPDXRef-Package-josephsoncircuits","name":"JosephsonCircuits.jl","versionInfo":"%s","licenseConcluded":"MIT"}]}\n' "${JOSEPHSONCIRCUITS_VERSION}" > /opt/textlayout/sbom.spdx.json \
    && chown -R appuser:appuser /solver-output /opt/textlayout

USER appuser
VOLUME ["/solver-output"]
CMD ["sh", "-lc", "cat /opt/textlayout/tool-identity.json"]
