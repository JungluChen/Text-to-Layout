"""Independent local-data assessment; no optional imports or execution claims."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from textlayout.external._squadds_metadata_worker import DATA_SHA256, HELPER_SHA256, VERSIONS


@dataclass(frozen=True)
class MetadataAssessment:
    """Data agreement only: this does not verify the producing process."""

    records_checked: int
    dataset_sha256: str
    evidence_status: str = "PRIOR_ONLY"
    physics_verified: bool = False


def assess_metadata(database: bytes, packet: dict[str, Any]) -> MetadataAssessment:
    """Reject mismatched raw metadata against exact pinned source bytes.

    No files, network, optional packages or processes are accessed. Raises
    ValueError on unsupported data/packet; returns data agreement only.
    """
    if len(database) > 1024 * 1024 or hashlib.sha256(database).hexdigest() != DATA_SHA256:
        raise ValueError("Expected pinned dataset bytes")
    rows = json.loads(database)
    columns = {
        "Design Code": "design_code", "Paper Link": "paper_link", "Image": "image",
        "Foundry": "foundry", "Substrate": "substrate", "Materials": "materials",
        "Junction Style": "junction_style", "Junction Materials": "junction_material",
    }
    records = [{"Name": row["contrib_info"]["name"],
                **{label: row[key] for label, key in columns.items()}} for row in rows]
    wm1 = next(row for row in rows if row["contrib_info"]["name"] == "WM1")
    info = wm1["contrib_info"]
    reference = {label: wm1[key] for label, key in {
        "Design Code": "design_code", "Paper Link": "paper_link", "Image": "image",
        "Foundry": "foundry", "Fabrication Recipe": "fabrication_recipe",
    }.items()}
    reference.update(info)
    contributor = {
        "Foundry": info.get("foundry", "N/A"), "PI": info["PI"], "Group": info["group"],
        "Institution": info["institution"], "Measured By": ", ".join(info["measured_by"]),
        "Reference Device Name": info["name"], "Uploader": info["uploader"],
    }
    expected: dict[str, Any] = {
        "schema": "textlayout.squadds-metadata-raw.v1", "evidence_status": "PRIOR_ONLY",
        "physics_verified": False, "assessment_status": "NOT_EVALUATED",
        "method": "installed SQuADDS db_devices helpers on local datasets.Dataset",
        "dataset_sha256": DATA_SHA256, "helper_sha256": HELPER_SHA256,
        "source_revision": "0e25705f54c343fb96571ff15b6fd8375ca899aa",
        "dependency_versions": VERSIONS, "records": records,
        "wm1_config_identifiers": wm1["sim_results"], "reference": reference,
        "contributor": contributor, "database_constructed": False,
        "electrical_reproduction_status": "NOT_EVALUATED",
    }
    if not isinstance(packet, dict) or set(packet) != set(expected) | {"python", "platform"}:
        raise ValueError("Unexpected metadata packet fields")
    for key in ("python", "platform"):
        if not isinstance(packet[key], str) or not packet[key].strip():
            raise ValueError(f"Missing runtime field: {key}")
    # JSON comparison distinguishes booleans from numbers (False != 0 here).
    try:
        actual = json.dumps({k: packet[k] for k in expected}, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid metadata JSON values") from exc
    if actual != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError("Metadata packet disagrees with pinned source or identity")
    return MetadataAssessment(len(records), DATA_SHA256)
