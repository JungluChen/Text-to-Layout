"""Generate release SPDX SBOM for the KLayout image with pinned Syft."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SYFT_VERSION = "1.46.0"
SYFT_GIT_COMMIT = "b15c5dbfe2bb21c9d73002c1056a829c8c411c75"
SYFT_IMAGE = "anchore/syft@sha256:473a60e3a58e29aca3aedb3e99e787bb4ef273917e44d10fcbea4330a07320bb"
SYFT_SOURCE_URL = "https://github.com/anchore/syft/archive/b15c5dbfe2bb21c9d73002c1056a829c8c411c75.tar.gz"
SYFT_SOURCE_SHA256 = "8bbbb3a27cca304c70192923834faa4c025b75a5ddbc9303ec5eed6e486e224a"
SYFT_SOURCE_SIZE_BYTES = 7045063
KLAYOUT_IMAGE = "textlayout/klayout@sha256:605d23699fb31ce852aadea98631474c117d59895810da3b359d9461607b12c0"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=False)


def image_id(image: str) -> str | None:
    result = run(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    return result.stdout.strip() if result.returncode == 0 else None


def evidence_command(command: list[str], output_directory: Path) -> list[str]:
    """Remove the local checkout path from the persisted Docker invocation."""
    return [item.replace(str(output_directory), "$OUTPUT_DIR") for item in command]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=KLAYOUT_IMAGE)
    parser.add_argument("--out", default="out/audit/klayout.syft.spdx.json")
    parser.add_argument("--evidence", default="out/audit/klayout_syft_sbom.json")
    args = parser.parse_args(argv)

    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "docker",
        "run",
        "--rm",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{out.parent}:/out",
        SYFT_IMAGE,
        args.image,
        "-o",
        f"spdx-json=/out/{out.name}",
    ]
    start = time.perf_counter()
    result = run(command)
    runtime = round(time.perf_counter() - start, 3)
    version = run(["docker", "run", "--rm", SYFT_IMAGE, "version"])
    payload: dict[str, Any] = {
        "schema": "textlayout.syft-sbom-generation.v1",
        "status": "SYFT_SBOM_GENERATED" if result.returncode == 0 and out.is_file() else "FAILED",
        "target_image": args.image,
        "target_image_digest": args.image.split("@", 1)[1] if "@" in args.image else image_id(args.image),
        "sbom_path": str(out.relative_to(REPO)).replace("\\", "/"),
        "sbom_sha256": sha256(out),
        "command": evidence_command(command, out.parent),
        "return_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "runtime_seconds": runtime,
        "generator": {
            "name": "syft",
            "version": SYFT_VERSION,
            "git_commit": SYFT_GIT_COMMIT,
            "image": SYFT_IMAGE,
            "license": "Apache-2.0",
            "source_archive_url": SYFT_SOURCE_URL,
            "source_archive_sha256": SYFT_SOURCE_SHA256,
            "source_archive_size_bytes": SYFT_SOURCE_SIZE_BYTES,
            "integration_role": "release SPDX 2.3 SBOM generation for KLayout OCI image",
            "version_stdout_sha256": hashlib.sha256(version.stdout.encode()).hexdigest(),
            "version_stderr_sha256": hashlib.sha256(version.stderr.encode()).hexdigest(),
        },
    }
    evidence = REPO / args.evidence
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["status"] == "SYFT_SBOM_GENERATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
