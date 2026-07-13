# syntax=docker/dockerfile:1.7
FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG KLAYOUT_VERSION=v0.30.9
ARG KLAYOUT_COMMIT=6270877110ef808dd442fd2244164cec06a7b10e
ARG KLAYOUT_SHA256=2d0582a893a1dbae50ed238b57b0ee76f3e4143f07b83b438d14cd612000bd63

LABEL org.opencontainers.image.title="Textlayout KLayout boundary" \
      org.opencontainers.image.description="Pinned KLayout identity boundary for DRC/LVS smoke" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${KLAYOUT_VERSION}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /opt/textlayout /solver-output \
    && printf '{"tool":"KLayout","version":"%s","commit":"%s","source_archive_sha256":"%s","status":"identity_recorded_not_solver_executed"}\n' "${KLAYOUT_VERSION}" "${KLAYOUT_COMMIT}" "${KLAYOUT_SHA256}" > /opt/textlayout/tool-identity.json \
    && printf '{"SPDXID":"SPDXRef-DOCUMENT","spdxVersion":"SPDX-2.3","name":"textlayout-klayout","packages":[{"SPDXID":"SPDXRef-Package-klayout","name":"KLayout","versionInfo":"%s","licenseConcluded":"GPL-3.0-or-later"}]}\n' "${KLAYOUT_VERSION}" > /opt/textlayout/sbom.spdx.json \
    && chown -R appuser:appuser /solver-output /opt/textlayout

USER appuser
VOLUME ["/solver-output"]
CMD ["sh", "-lc", "cat /opt/textlayout/tool-identity.json"]
