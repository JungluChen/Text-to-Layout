"""Shared helpers for the external tool registry scripts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
REGISTRY = ROOT / "external_tools" / "registry.toml"
LOCK = ROOT / "external_tools" / "lock.toml"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
TOOLCHAIN_OUT = ROOT / "out" / "toolchain"
SOURCE_CACHE = ROOT / ".tools" / "external" / "sources"

REQUIRED_FIELDS = (
    "id",
    "canonical_name",
    "upstream_repository",
    "pinned_ref",
    "pinned_commit",
    "source_archive_url",
    "source_archive_sha256",
    "source_archive_size_bytes",
    "spdx_license",
    "copyright_holder",
    "install_mode",
    "integration_mode",
    "redistribute_source",
    "redistribute_binaries",
    "adapter_module",
    "smoke_test_command",
    "benchmark_command",
    "supported_operating_systems",
    "required_runtime",
    "expected_output_files",
)

STATUS_ORDER = (
    "REGISTERED",
    "DOWNLOADED",
    "LICENSE_REVIEWED",
    "INSTALLED",
    "IDENTITY_VERIFIED",
    "SMOKE_TEST_PASSED",
    "BENCHMARK_EXECUTED",
    "INTEGRATED",
    "SCIENTIFICALLY_VALIDATED",
)


@dataclass(frozen=True)
class Registry:
    policy: dict[str, Any]
    tools: list[dict[str, Any]]
    locked: dict[str, dict[str, Any]]


def load_registry() -> Registry:
    registry = tomllib.loads(REGISTRY.read_text(encoding="utf-8"))
    lock = tomllib.loads(LOCK.read_text(encoding="utf-8"))
    return Registry(
        policy=dict(registry.get("policy", {})),
        tools=list(registry.get("tools", [])),
        locked={tool["id"]: tool for tool in lock.get("locked_tools", [])},
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_archive_path(tool: dict[str, Any]) -> Path:
    return SOURCE_CACHE / f"{tool['id']}-{tool['pinned_commit']}.tar.gz"


def download_archive(tool: dict[str, Any]) -> dict[str, Any]:
    SOURCE_CACHE.mkdir(parents=True, exist_ok=True)
    target = source_archive_path(tool)
    if not target.exists():
        request = urllib.request.Request(
            str(tool["source_archive_url"]), headers={"User-Agent": "textlayout-toolchain"}
        )
        with urllib.request.urlopen(request, timeout=600) as response, target.open("wb") as out:
            shutil.copyfileobj(response, out)
    actual = sha256_file(target)
    expected = str(tool["source_archive_sha256"])
    if actual != expected:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"{tool['id']}: source archive checksum mismatch: expected {expected}, got {actual}"
        )
    return {
        "tool": tool["id"],
        "archive": str(target.relative_to(ROOT)),
        "sha256": actual,
        "size_bytes": target.stat().st_size,
        "status": "DOWNLOADED",
    }


def adapter_importable(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def command_available(command: list[str]) -> bool:
    if not command:
        return False
    executable = command[0]
    if executable in {"py", "python", sys.executable}:
        return True
    if executable == "julia":
        return shutil.which("julia") is not None
    return shutil.which(executable) is not None


def installed_for_smoke(command: list[str]) -> bool:
    """Best-effort installed check without promoting a failed smoke test.

    For Python smoke commands of the form ``py -c "import module"``, executable
    availability is not enough: the module itself must be importable.
    """
    if len(command) >= 4 and command[0] in {"py", "python", sys.executable} and command[2] == "-c":
        source = command[3]
        marker = "import "
        if marker in source:
            module = source.split(marker, 1)[1].split(";", 1)[0].split()[0].strip()
            return importlib.util.find_spec(module) is not None
    return command_available(command)


def run_command(command: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    started_command = [str(part) for part in command]
    try:
        completed = subprocess.run(
            started_command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": started_command,
            "return_code": None,
            "passed": False,
            "reason": str(exc),
        }
    return {
        "command": started_command,
        "return_code": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def validate_registry(registry: Registry) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for tool in registry.tools:
        missing = [field for field in REQUIRED_FIELDS if field not in tool]
        if missing:
            problems.append(f"{tool.get('id', '<missing id>')}: missing fields {missing}")
        tool_id = str(tool.get("id", ""))
        if tool_id in seen:
            problems.append(f"{tool_id}: duplicate tool id")
        seen.add(tool_id)
        if tool_id not in registry.locked:
            problems.append(f"{tool_id}: missing lock entry")
            continue
        locked = registry.locked[tool_id]
        for key in ("resolved_commit", "source_archive_sha256", "source_archive_url"):
            if str(locked.get(key)) != str(
                tool.get("pinned_commit" if key == "resolved_commit" else key)
            ):
                problems.append(f"{tool_id}: registry/lock mismatch for {key}")
        for key in ("binary_archive_url", "binary_archive_sha256", "binary_archive_size_bytes"):
            if key in tool and str(locked.get(key)) != str(tool.get(key)):
                problems.append(f"{tool_id}: registry/lock mismatch for {key}")
        sha = str(tool.get("source_archive_sha256", ""))
        if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
            problems.append(f"{tool_id}: invalid source_archive_sha256")
        if str(tool.get("spdx_license")) == "NOASSERTION" and not tool.get(
            "human_review_required"
        ):
            problems.append(f"{tool_id}: NOASSERTION license requires human_review_required")
        if str(tool.get("spdx_license", "")).startswith("GPL") and "file exchange" not in str(
            tool.get("integration_mode", "")
        ):
            problems.append(f"{tool_id}: GPL integration must stay process/file isolated")
        if tool.get("redistribute_binaries") is True:
            problems.append(f"{tool_id}: registry must not redistribute binaries")
    locked_ids = set(registry.locked)
    extra = sorted(locked_ids - seen)
    if extra:
        problems.append(f"lock has entries not in registry: {extra}")
    return problems


def tool_status(tool: dict[str, Any], *, smoke: bool, benchmark: bool) -> dict[str, Any]:
    statuses = ["REGISTERED"]
    archive = source_archive_path(tool)
    archive_problem = None
    if archive.is_file():
        actual = sha256_file(archive)
        if actual == tool["source_archive_sha256"]:
            statuses.append("DOWNLOADED")
        else:
            archive_problem = f"cache checksum mismatch: {actual}"
    if tool["spdx_license"] != "NOASSERTION":
        statuses.append("LICENSE_REVIEWED")
    retained_state: str | None = None
    retained_identity: dict[str, Any] | None = None
    if tool["id"] == "palace":
        from check_palace import check as check_palace

        retained = check_palace()
        retained_state = str(retained["state"])
        installation = retained.get("installation")
        retained_identity = installation if isinstance(installation, dict) else None
    elif tool["id"] == "paraview":
        from check_paraview import check as check_paraview

        retained = check_paraview()
        retained_state = str(retained["state"])
        identity = retained.get("identity")
        retained_identity = identity if isinstance(identity, dict) else None
    installed = (
        retained_identity is not None
        if tool["id"] in {"palace", "paraview"}
        else installed_for_smoke(list(tool["smoke_test_command"]))
    )
    if installed:
        statuses.append("INSTALLED")
    if retained_identity is not None:
        statuses.append("IDENTITY_VERIFIED")
    integrated = adapter_importable(str(tool["adapter_module"]))
    if integrated:
        statuses.append("INTEGRATED")
    smoke_result: dict[str, Any] | None = None
    if retained_state in {"SMOKE_TEST_PASSED", "BENCHMARK_EXECUTED"}:
        statuses.append("SMOKE_TEST_PASSED")
        smoke_result = {"status": "retained_hash_verified", "passed": True}
    if smoke and installed:
        smoke_result = run_command(list(tool["smoke_test_command"]), timeout_seconds=120)
        if smoke_result["passed"]:
            statuses.append("SMOKE_TEST_PASSED")
    benchmark_result: dict[str, Any] | None = None
    if retained_state == "BENCHMARK_EXECUTED":
        statuses.append("BENCHMARK_EXECUTED")
        benchmark_result = {"status": "retained_hash_verified", "passed": True}
    if benchmark:
        benchmark_result = run_command(list(tool["benchmark_command"]), timeout_seconds=600)
        if benchmark_result["passed"]:
            statuses.append("BENCHMARK_EXECUTED")
    return {
        "id": tool["id"],
        "canonical_name": tool["canonical_name"],
        "statuses": [status for status in STATUS_ORDER if status in statuses],
        "license": tool["spdx_license"],
        "integration_mode": tool["integration_mode"],
        "install_mode": tool["install_mode"],
        "adapter_module": tool["adapter_module"],
        "adapter_importable": integrated,
        "identity": retained_identity,
        "archive_cache": str(archive.relative_to(ROOT)),
        "archive_problem": archive_problem,
        "smoke_test": smoke_result or {"status": "not_run"},
        "benchmark": benchmark_result or {"status": "not_run"},
        "expected_output_files": list(tool["expected_output_files"]),
        "human_review_required": bool(tool.get("human_review_required", False)),
        "scientifically_validated": "SCIENTIFICALLY_VALIDATED" in statuses,
    }


def license_report(registry: Registry) -> dict[str, Any]:
    return {
        "schema": "textlayout.external-tools.license-report.v1",
        "policy": registry.policy,
        "tools": [
            {
                "id": tool["id"],
                "canonical_name": tool["canonical_name"],
                "spdx_license": tool["spdx_license"],
                "copyright_holder": tool["copyright_holder"],
                "integration_mode": tool["integration_mode"],
                "redistribute_source": tool["redistribute_source"],
                "redistribute_binaries": tool["redistribute_binaries"],
                "human_review_required": bool(tool.get("human_review_required", False)),
                "dataset_license": tool.get("dataset_license", "not_recorded"),
            }
            for tool in registry.tools
        ],
    }


def sbom(registry: Registry) -> dict[str, Any]:
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "Text-to-Layout external tool registry",
        "documentNamespace": "https://github.com/JungluChen/Text-to-Layout/external-tools",
        "packages": [
            {
                "SPDXID": f"SPDXRef-Package-{tool['id']}",
                "name": tool["canonical_name"],
                "downloadLocation": tool["source_archive_url"],
                "versionInfo": tool["pinned_ref"],
                "licenseConcluded": tool["spdx_license"],
                "licenseDeclared": tool["spdx_license"],
                "checksums": [
                    {
                        "algorithm": "SHA256",
                        "checksumValue": tool["source_archive_sha256"],
                    }
                ],
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:github/{tool['upstream_repository'].removeprefix('https://github.com/')}",
                    }
                ],
            }
            for tool in registry.tools
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def selected_tools(registry: Registry, ids: list[str] | None) -> list[dict[str, Any]]:
    if not ids:
        return registry.tools
    wanted = set(ids)
    tools = [tool for tool in registry.tools if tool["id"] in wanted]
    missing = sorted(wanted - {tool["id"] for tool in tools})
    if missing:
        raise SystemExit(f"unknown external tool id(s): {', '.join(missing)}")
    return tools


def parser_with_tools(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--tool", action="append", dest="tools", help="tool id; repeatable")
    return parser


def on_windows() -> bool:
    return os.name == "nt"
