"""Validate a generated SPDX SBOM with pinned spdx-tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--infile", default="out/audit/klayout.sbom.spdx.json")
    parser.add_argument("--out", default="out/audit/klayout_sbom_validation.json")
    args = parser.parse_args(argv)

    infile = Path(args.infile)
    out = Path(args.out)
    command = [
        "uvx",
        "--from",
        "spdx-tools==0.8.3",
        "pyspdxtools",
        "--infile",
        str(infile),
        "--version",
        "SPDX-2.3",
    ]
    start = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    payload: dict[str, Any] = {
        "schema": "textlayout.sbom-validation.v1",
        "status": "SBOM_SCHEMA_VALIDATED" if result.returncode == 0 else "SBOM_SCHEMA_VALIDATION_FAILED",
        "sbom_path": str(infile).replace("\\", "/"),
        "sbom_sha256": sha256(infile),
        "validator": {
            "name": "spdx-tools",
            "version": "0.8.3",
            "command": command,
            "return_code": result.returncode,
            "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
            "runtime_seconds": round(time.perf_counter() - start, 3),
        },
        "validated_gates": {
            "valid_spdx_version": result.returncode == 0,
            "document_namespace": result.returncode == 0,
            "package_identifiers": result.returncode == 0,
            "relationships": result.returncode == 0,
            "checksums": result.returncode == 0,
            "creator_information": result.returncode == 0,
            "image_digest_linkage": False,
            "klayout_package_presence": False,
            "klayout_version_0_30_9": False,
            "base_os_identity": False,
        },
        "failure_reason": None if result.returncode == 0 else (result.stderr.strip() or result.stdout.strip()),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
