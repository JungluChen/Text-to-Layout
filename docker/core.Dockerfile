# syntax=docker/dockerfile:1.7
FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db

ARG SOURCE_REVISION=e09e901fc392079b6dc6c7e5160654ef4da50397
ARG SOURCE_VERSION=0.3.0

LABEL org.opencontainers.image.title="Textlayout core" \
      org.opencontainers.image.description="Open-source Text-to-Layout core smoke image" \
      org.opencontainers.image.source="https://github.com/JungluChen/Text-to-Layout" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.version="${SOURCE_VERSION}" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /workspace
COPY pyproject.toml uv.lock README.md THIRD_PARTY_NOTICES.md ./
COPY src ./src

RUN useradd --create-home --uid 10001 appuser \
    && python -m compileall -q src/textlayout \
    && mkdir -p /opt/textlayout \
    && python -c "import json, pathlib, platform; pathlib.Path('/opt/textlayout/sbom.spdx.json').write_text(json.dumps({'SPDXID':'SPDXRef-DOCUMENT','spdxVersion':'SPDX-2.3','name':'textlayout-core','creationInfo':{'creators':['Tool: textlayout-dockerfile'],'created':'1970-01-01T00:00:00Z'},'packages':[{'SPDXID':'SPDXRef-Package-textlayout','name':'text-to-gds','versionInfo':'0.3.0','licenseConcluded':'MIT'},{'SPDXID':'SPDXRef-Package-python','name':'python','versionInfo':platform.python_version(),'licenseConcluded':'Python-2.0'}]}, indent=2) + '\n', encoding='utf-8')" \
    && python -c "import json, pathlib, platform; pathlib.Path('/opt/textlayout/package-identity.json').write_text(json.dumps({'image':'textlayout/core','source_revision':'${SOURCE_REVISION}','python':platform.python_version()}, indent=2) + '\n', encoding='utf-8')"

USER appuser
ENV PYTHONPATH=/workspace/src
CMD ["python", "-c", "import json, pathlib; print(pathlib.Path('/opt/textlayout/package-identity.json').read_text())"]
