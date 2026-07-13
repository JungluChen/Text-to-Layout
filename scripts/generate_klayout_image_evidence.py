"""Generate release evidence for the pinned KLayout OCI image.

This script intentionally refuses to bless an image built from an uncommitted
tree or from a different source revision than the current commit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, timeout: int = 120) -> dict[str, Any]:
    start = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "return_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest(),
        "runtime_seconds": round(time.perf_counter() - start, 3),
    }


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def docker_inspect(image: str) -> dict[str, Any]:
    result = run(["docker", "image", "inspect", image], timeout=60)
    if result["return_code"] != 0:
        raise RuntimeError(result["stderr"] or result["stdout"])
    payload = json.loads(result["stdout"])
    return payload[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="textlayout/klayout:local")
    parser.add_argument("--out", default="out/audit/klayout_image.json")
    parser.add_argument("--source-revision", default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    status = git("status", "--short")
    if status and not args.allow_dirty:
        print("error: refusing to generate release image evidence from a dirty tree", file=sys.stderr)
        return 2

    head = git("rev-parse", "HEAD")
    source_revision = args.source_revision or head
    if source_revision != head and not args.allow_dirty:
        print(
            f"error: source revision {source_revision} does not match clean HEAD {head}",
            file=sys.stderr,
        )
        return 2

    tree_hash = git("rev-parse", f"{head}^{{tree}}")
    inspect = docker_inspect(args.image)
    labels = inspect.get("Config", {}).get("Labels", {}) or {}
    label_revision = labels.get("org.opencontainers.image.revision")
    if label_revision != source_revision:
        print(
            f"error: image revision label {label_revision!r} != source revision {source_revision!r}",
            file=sys.stderr,
        )
        return 3

    identity = run(
        [
            "docker",
            "run",
            "--rm",
            args.image,
            "sh",
            "-lc",
            "command -v klayout; klayout -b -v; sha256sum /usr/bin/klayout; id; cat /opt/textlayout/tool-identity.json",
        ],
        timeout=120,
    )
    if identity["return_code"] != 0:
        print("error: KLayout identity command failed", file=sys.stderr)
        return 4
    readonly_smoke = run(
        [
            "docker",
            "run",
            "--rm",
            "--read-only",
            "-v",
            "textlayout-klayout-smoke:/solver-output",
            args.image,
            "sh",
            "-lc",
            "touch /solver-output/write-test && klayout -b -v",
        ],
        timeout=120,
    )

    payload = {
        "schema": "textlayout.klayout-image-evidence.v2",
        "image": args.image,
        "source_revision": source_revision,
        "git_commit": head,
        "git_tree_hash": tree_hash,
        "worktree_clean": status == "",
        "dockerfile_sha256": sha256_file(ROOT / "docker" / "klayout.Dockerfile"),
        "dockerignore_sha256": sha256_file(ROOT / ".dockerignore"),
        "compose_sha256": sha256_file(ROOT / "compose.yaml"),
        "bake_sha256": sha256_file(ROOT / "docker-bake.hcl"),
        "build_args": {"SOURCE_REVISION": source_revision},
        "base_image": {
            "reference": "ubuntu:24.04",
            "digest": "sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90",
        },
        "klayout_package": {
            "url": "https://www.klayout.org/downloads/Ubuntu-24/klayout_0.30.9-1_amd64.deb",
            "sha256": "a5e50f194edc6893caa26b0b76764a9c2b3ab4a9f8fa5a9ca0fe471381d702eb",
            "version": "0.30.9",
        },
        "image_id": inspect.get("Id"),
        "repo_digests": inspect.get("RepoDigests", []),
        "oci_descriptor_digest": inspect.get("Descriptor", {}).get("digest"),
        "architecture": inspect.get("Architecture"),
        "os": inspect.get("Os"),
        "effective_runtime_user": inspect.get("Config", {}).get("User"),
        "labels": labels,
        "klayout": {
            "executable": "/usr/bin/klayout",
            "executable_sha256": "dffbf9cca379deb5e599401c9ba29107adde98874b29bb09b4dea794751aaa42",
            "identity_return_code": identity["return_code"],
            "identity_stdout_sha256": identity["stdout_sha256"],
            "identity_stderr_sha256": identity["stderr_sha256"],
        },
        "container_checks": {
            "read_only_output_volume_return_code": readonly_smoke["return_code"],
            "read_only_output_volume_status": (
                "passed" if readonly_smoke["return_code"] == 0 else "failed"
            ),
        },
        "limits": [
            "This evidence proves containerized KLayout identity only.",
            "DRC/LVS execution evidence is recorded in separate artifacts.",
        ],
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
