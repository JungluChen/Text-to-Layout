"""PDK provenance records: what every report must carry.

The file hash is deliberately NOT a field on :class:`PDK` itself — it is a
property of the *file* a PDK was loaded from, not of the parsed content (the
same content re-serialized would hash differently). This module is the one
place that reads a PDK file's bytes and its parsed content together, so
"which exact file backed this report" is always answerable and byte-exact,
not just "which PDK name" (which could silently drift if the file changes
without a version bump).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from textlayout.pdk.loader import load_pdk
from textlayout.pdk.models import PDK

PDK_PROVENANCE_SCHEMA = "textlayout.pdk-provenance.v1"


class PDKProvenance(BaseModel):
    """The exact record every generated report should embed for its PDK."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=PDK_PROVENANCE_SCHEMA)
    pdk_name: str
    pdk_version: str
    file_path: str
    file_hash_sha256: str
    calibration_status: str
    foundry_validated: bool
    source: str


def describe_pdk_file(path: str | Path) -> PDKProvenance:
    """Load a PDK file and compute its exact provenance record."""
    file_path = Path(path)
    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    pdk = load_pdk(file_path)
    return PDKProvenance(
        pdk_name=pdk.name,
        pdk_version=pdk.version,
        file_path=str(file_path),
        file_hash_sha256=digest,
        calibration_status=pdk.calibration_status,
        foundry_validated=pdk.foundry_validated,
        source=pdk.source,
    )


def find_pdk_provenance_for_technology(technology_name: str) -> PDKProvenance | None:
    """Look up the PDK backing a registered technology name, if any.

    Returns ``None`` for technologies not backed by a PDK YAML (e.g. the
    hardcoded built-in ``generic_2metal`` — that absence is itself an honest
    signal: a report for it should say "no PDK provenance available", not
    silently omit the field.
    """
    from textlayout.knowledge.technology_library import PDKS_DIR

    for pdk_path in sorted(PDKS_DIR.glob("*.yaml")):
        try:
            provenance = describe_pdk_file(pdk_path)
        except Exception:  # noqa: BLE001 - a malformed file must not crash report generation
            continue
        if provenance.pdk_name == technology_name:
            return provenance
    return None


def pdk_from_provenance(provenance: PDKProvenance) -> PDK:
    """Re-load the full PDK object a provenance record points to."""
    return load_pdk(provenance.file_path)
