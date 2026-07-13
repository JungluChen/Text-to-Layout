"""Execute committed DRC fixtures with the generated deck inside the KLayout image."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from textlayout.pdk.klayout_drc import compile_drc_rules, run_drc
from textlayout.pdk.loader import load_pdk

REPO = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = "textlayout/klayout@sha256:605d23699fb31ce852aadea98631474c117d59895810da3b359d9461607b12c0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_lyrdb(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    categories = [
        (category.findtext("name") or "").strip("'")
        for category in root.findall("./categories/category")
    ]
    items: list[dict[str, Any]] = []
    for item in root.findall("./items/item"):
        category = (item.findtext("category") or "").strip("'")
        values = [value.text or "" for value in item.findall("./values/value")]
        items.append({"category": category, "values": values})
    counts: dict[str, int] = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return {
        "categories": sorted(categories),
        "items": items,
        "rule_ids": sorted(counts),
        "violation_counts_by_rule": dict(sorted(counts.items())),
    }


def docker_image_digest(image: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def klayout_sha256(image: str) -> str | None:
    result = subprocess.run(
        ["docker", "run", "--rm", image, "sh", "-lc", "sha256sum /usr/bin/klayout"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.split()[0]


def run_fixture(image: str, fixture: dict[str, Any], manifest: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    pdk = load_pdk(REPO / manifest["pdk"])
    gds = REPO / fixture["path"]
    runset = REPO / manifest["runset"]
    fixture_out = out_dir / fixture["name"]
    fixture_out.mkdir(parents=True, exist_ok=True)
    lyrdb = fixture_out / f"{fixture['name']}.lyrdb"
    stdout = fixture_out / "stdout.txt"
    stderr = fixture_out / "stderr.txt"
    command = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{REPO}:/work:ro",
        "-v",
        f"{fixture_out}:/out",
        image,
        "sh",
        "-lc",
        (
            "cp /work/"
            + manifest["runset"]
            + " /tmp/compiled.drc && "
            "klayout -b /work/"
            + fixture["path"]
            + " -r /tmp/compiled.drc -rd report=/out/"
            + lyrdb.name
        ),
    ]
    start = time.perf_counter()
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=False)
    runtime = round(time.perf_counter() - start, 6)
    stdout.write_text(result.stdout, encoding="utf-8")
    stderr.write_text(result.stderr, encoding="utf-8")
    parsed = parse_lyrdb(lyrdb) if lyrdb.is_file() else {
        "categories": [],
        "items": [],
        "rule_ids": [],
        "violation_counts_by_rule": {},
    }
    python_report = run_drc(pdk, gds, top_cell=fixture["top_cell"])
    python_ids = sorted({violation.rule_id for violation in python_report.violations})
    python_violation_count = sum(violation.count for violation in python_report.violations)
    standalone_ids = parsed["rule_ids"]
    expected = sorted(fixture["expected_rule_ids"])
    unexpected = sorted(set(standalone_ids) - set(expected))
    standalone_passed = (
        result.returncode == 0
        and lyrdb.is_file()
        and set(expected) <= set(standalone_ids)
        and len(unexpected) <= fixture["max_unexpected_violations"]
        and (bool(expected) or not standalone_ids)
    )
    return {
        "fixture": fixture["name"],
        "status": "passed" if standalone_passed else "failed",
        "image": image,
        "image_id": docker_image_digest(image),
        "klayout_executable_sha256": klayout_sha256(image),
        "gds_sha256": sha256(gds),
        "pdk_hash": manifest["pdk_hash"],
        "compiled_rule_hash": sha256_text(
            json.dumps([rule.to_dict() for rule in compile_drc_rules(pdk)], sort_keys=True)
        ),
        "lydrc_sha256": sha256(runset),
        "command": command,
        "return_code": result.returncode,
        "stdout_sha256": sha256(stdout),
        "stderr_sha256": sha256(stderr),
        "lyrdb_path": str(lyrdb.relative_to(REPO)).replace("\\", "/") if lyrdb.is_file() else None,
        "lyrdb_sha256": sha256(lyrdb) if lyrdb.is_file() else None,
        "parsed_summary_sha256": sha256_text(json.dumps(parsed, sort_keys=True)),
        "runtime_seconds": runtime,
        "expected_rule_ids": expected,
        "python_rule_ids": python_ids,
        "standalone_rule_ids": standalone_ids,
        "python_backend_passed": set(expected) <= set(python_ids) and (bool(expected) or not python_ids),
        "standalone_backend_passed": standalone_passed,
        "rule_id_parity": set(python_ids) == set(standalone_ids),
        "violation_count_parity": python_violation_count == len(parsed["items"]),
        "bbox_parity_within_tolerance": None,
        "parsed_summary": parsed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--manifest", default="tests/fixtures/klayout_drc/expectations.json")
    parser.add_argument("--out", default="out/audit/klayout_containerized_drc.json")
    parser.add_argument("--reports-dir", default="out/audit/klayout_lyrdb")
    args = parser.parse_args(argv)

    manifest = json.loads((REPO / args.manifest).read_text(encoding="ascii"))
    reports_dir = REPO / args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)
    rows = [run_fixture(args.image, fixture, manifest, reports_dir) for fixture in manifest["fixtures"]]
    payload = {
        "schema": "textlayout.klayout-containerized-drc.v1",
        "image": args.image,
        "image_id": docker_image_digest(args.image),
        "fixture_expectations_passed": all(row["standalone_backend_passed"] for row in rows),
        "all_rule_id_parity": all(row["rule_id_parity"] for row in rows),
        "all_violation_count_parity": all(row["violation_count_parity"] for row in rows),
        "fixtures": rows,
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["fixture_expectations_passed"] and payload["all_rule_id_parity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
