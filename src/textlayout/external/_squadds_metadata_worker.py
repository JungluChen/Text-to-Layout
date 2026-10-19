"""Optional-runtime offline SQuADDS metadata worker; no electrical acceptance."""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

DATA_SHA256 = "898a27f0eadaf687129a7bb85971f891c967515764dc7d27f684e669edea1069"
HELPER_SHA256 = "dea8dd7f2a7c949c21794a7fbe333253f2a6f9f310f4d2e1f99e35623e3f760c"
VERSIONS = {"squadds": "0.4.5", "datasets": "5.0.1", "pyarrow": "21.0.0",
            "numpy": "1.26.4", "pandas": "2.3.3"}


def execute(database: Path, output: Path) -> None:
    """Read pinned local bytes and write a new raw packet via normal imports.

    Requires an explicit isolated interpreter with the audited optional stack.
    Never constructs SQuADDS_DB or fetches a dataset. Existing outputs refused.
    """
    if output.exists():
        raise FileExistsError(output)
    with database.open("rb") as stream:
        payload = stream.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024 or hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise ValueError("Expected pinned WM1 dataset bytes (maximum 1 MiB)")
    versions = {name: importlib.metadata.version(name) for name in VERSIONS}
    if versions != VERSIONS:
        raise ValueError("Unsupported optional runtime versions")
    dist = importlib.metadata.distribution("squadds")
    helper_path = Path(str(dist.locate_file("squadds/core/db_devices.py")))
    if hashlib.sha256(helper_path.read_bytes()).hexdigest() != HELPER_SHA256:
        raise ValueError("Installed SQuADDS helper hash mismatch")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    upstream = importlib.import_module("squadds.core.db_devices")
    if upstream.__file__ is None or Path(upstream.__file__).resolve() != helper_path.resolve():
        raise ValueError("Imported helper differs from installed distribution")
    datasets = importlib.import_module("datasets")
    rows = json.loads(payload)
    dataset = datasets.Dataset.from_list(rows)
    records = upstream.build_measured_device_records(dataset)
    # Keep this helper's observed discrepancy, rather than inventing a correction.
    config = "cavity_claw-RouteMeander-eigenmode"
    packet: dict[str, Any] = {
        "schema": "textlayout.squadds-metadata-raw.v1",
        "evidence_status": "PRIOR_ONLY", "physics_verified": False,
        "assessment_status": "NOT_EVALUATED",
        "method": "installed SQuADDS db_devices helpers on local datasets.Dataset",
        "dataset_sha256": DATA_SHA256, "helper_sha256": HELPER_SHA256,
        "source_revision": "0e25705f54c343fb96571ff15b6fd8375ca899aa",
        "dependency_versions": versions, "python": sys.version,
        "platform": platform.platform(), "records": records,
        "wm1_config_identifiers": upstream.find_simulation_results_for_device(dataset, "WM1"),
        "reference": upstream.find_reference_device_info(dataset, config),
        "contributor": upstream.find_device_contributor_info(dataset, config),
        "database_constructed": False, "electrical_reproduction_status": "NOT_EVALUATED",
    }
    encoded = json.dumps(packet, indent=2, allow_nan=False) + "\n"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: _squadds_metadata_worker.py DATABASE NEW_OUTPUT.json")
    execute(Path(sys.argv[1]), Path(sys.argv[2]))
