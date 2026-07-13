"""Validate Docker and Syft SPDX SBOMs with pinned spdx-tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

KLAYOUT_DIGEST = "sha256:605d23699fb31ce852aadea98631474c117d59895810da3b359d9461607b12c0"


def _sanitize_text(text: str) -> str:
    sanitized = text
    replacements = {
        str(Path.home()): "<HOME>",
        str(Path.cwd()): "<REPO>",
        str(Path.home()).replace("\\", "\\\\"): "<HOME>",
        str(Path.cwd()).replace("\\", "\\\\"): "<REPO>",
    }
    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)
    return sanitized


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_spdx_tools(path: Path) -> dict[str, Any]:
    command = [
        "uvx",
        "--from",
        "spdx-tools==0.8.3",
        "pyspdxtools",
        "--infile",
        str(path),
        "--version",
        "SPDX-2.3",
    ]
    start = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "command": command,
        "return_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "runtime_seconds": round(time.perf_counter() - start, 3),
        "failure_reason": None if result.returncode == 0 else _sanitize_text(
            result.stderr.strip() or result.stdout.strip()
        ),
    }


def _semantic_gates(path: Path, parser_ok: bool, expected_digest: str) -> dict[str, bool]:
    if not parser_ok or not path.is_file():
        return {
            "valid_spdx_version": False,
            "document_namespace": False,
            "package_identifiers": False,
            "relationships": False,
            "checksums": False,
            "creator_information": False,
            "image_digest_linkage": False,
            "klayout_package_presence": False,
            "klayout_version_0_30_9": False,
            "base_os_identity": False,
            "scanned_image_digest_recorded": False,
            "sbom_hash_recorded": bool(sha256(path)),
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    packages = payload.get("packages", [])
    root_packages = [
        package for package in packages
        if package.get("name") == "textlayout/klayout"
    ]
    klayout_packages = [
        package for package in packages
        if package.get("name") == "klayout"
    ]
    base_packages = [
        package for package in packages
        if package.get("name") in {"base-files", "ubuntu"}
    ]
    package_ids = [package.get("SPDXID") for package in packages]
    relationships = payload.get("relationships", [])
    root = root_packages[0] if root_packages else {}
    root_version = str(root.get("versionInfo", ""))
    root_refs = json.dumps(root.get("externalRefs", []), sort_keys=True)
    return {
        "valid_spdx_version": payload.get("spdxVersion") == "SPDX-2.3",
        "document_namespace": bool(payload.get("documentNamespace", "").startswith("https://")),
        "package_identifiers": bool(package_ids) and all(str(value).startswith("SPDXRef-") for value in package_ids),
        "relationships": bool(relationships),
        "checksums": any(package.get("checksums") or package.get("packageVerificationCode") for package in packages),
        "creator_information": bool(payload.get("creationInfo", {}).get("creators")),
        "image_digest_linkage": expected_digest in root_version or expected_digest.replace("sha256:", "") in root_refs,
        "klayout_package_presence": bool(klayout_packages),
        "klayout_version_0_30_9": any(
            str(package.get("versionInfo", "")).startswith("0.30.9")
            for package in klayout_packages
        ),
        "base_os_identity": bool(base_packages),
        "scanned_image_digest_recorded": expected_digest in root_version,
        "sbom_hash_recorded": bool(sha256(path)),
    }


def _validate_one(path: Path, expected_digest: str) -> dict[str, Any]:
    parser = _run_spdx_tools(path)
    parser_ok = parser["return_code"] == 0
    gates = _semantic_gates(path, parser_ok, expected_digest)
    return {
        "sbom_path": str(path).replace("\\", "/"),
        "sbom_sha256": sha256(path),
        "parser_valid": parser_ok,
        "semantic_valid": all(gates.values()),
        "validator": {
            "name": "spdx-tools",
            "version": "0.8.3",
            **parser,
        },
        "validated_gates": gates,
        "failure_reason": parser["failure_reason"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker-infile", default="out/audit/klayout.sbom.spdx.json")
    parser.add_argument("--syft-infile", default="out/audit/klayout.syft.spdx.json")
    parser.add_argument("--expected-image-digest", default=KLAYOUT_DIGEST)
    parser.add_argument("--out", default="out/audit/klayout_sbom_validation.json")
    args = parser.parse_args(argv)

    docker_result = _validate_one(Path(args.docker_infile), args.expected_image_digest)
    syft_result = _validate_one(Path(args.syft_infile), args.expected_image_digest)
    payload: dict[str, Any] = {
        "schema": "textlayout.sbom-validation.v2",
        "docker_sbom_valid": docker_result["parser_valid"] and docker_result["semantic_valid"],
        "syft_sbom_valid": syft_result["parser_valid"] and syft_result["semantic_valid"],
        "release_sbom_generator": "syft",
        "release_sbom_valid": syft_result["parser_valid"] and syft_result["semantic_valid"],
        "docker_sbom": docker_result,
        "syft_sbom": syft_result,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["release_sbom_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
