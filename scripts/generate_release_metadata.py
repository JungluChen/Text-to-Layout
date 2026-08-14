#!/usr/bin/env python3
"""Generate compact SPDX SBOM and in-toto provenance for built distributions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_metadata(dist: Path, *, root: Path = ROOT) -> tuple[dict[str, object], dict[str, object]]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    artifacts = [
        {"name": path.name, "digest": {"sha256": sha256_file(path)}}
        for path in sorted(dist.iterdir())
        if path.is_file()
    ]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    commit_epoch = int(
        subprocess.run(
            ["git", "show", "-s", "--format=%ct", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    created = datetime.fromtimestamp(commit_epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    version = str(project["version"])
    name = str(project["name"])
    sbom: dict[str, object] = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{name}-{version}",
        "documentNamespace": f"https://github.com/JungluChen/Text-to-Layout/releases/tag/v{version}",
        "creationInfo": {
            "created": created,
            "creators": ["Tool: scripts/generate_release_metadata.py"],
        },
        "packages": [
            {
                "name": name,
                "SPDXID": "SPDXRef-Package",
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "MIT",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{name}@{version}",
                    }
                ],
            }
        ],
    }
    provenance: dict[str, object] = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": artifacts,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/JungluChen/Text-to-Layout/.github/workflows/release.yml",
                "externalParameters": {"version": version},
                "resolvedDependencies": [
                    {
                        "uri": "git+https://github.com/JungluChen/Text-to-Layout",
                        "digest": {"gitCommit": commit},
                    }
                ],
            },
            "runDetails": {
                "builder": {"id": "https://github.com/actions/runner"},
                "metadata": {"invocationId": commit},
            },
        },
    }
    return sbom, provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path, default=ROOT / "release")
    args = parser.parse_args(argv)
    sbom, provenance = build_metadata(args.dist.resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "sbom.spdx.json").write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output / "provenance.intoto.jsonl").write_text(
        json.dumps(provenance, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
