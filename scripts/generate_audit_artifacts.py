"""Generate machine-readable project audit artifacts.

The outputs are intentionally conservative. File existence, parsed metadata,
or a successful unit test are recorded as evidence, but never promoted to
solver execution, numerical convergence, or physics verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "out" / "audit"
START_COMMIT = "ff3bbb4b30f2523fb32fffa4d2170c34768e0d4d"

VERIFICATION_LADDER = [
    "NOT_IMPLEMENTED",
    "IMPLEMENTED",
    "UNIT_TESTED",
    "REAL_FIXTURE_TESTED",
    "FRESH_ENVIRONMENT_TESTED",
    "UPSTREAM_SMOKE_PASSED",
    "INTEGRATION_TEST_PASSED",
    "REAL_BENCHMARK_EXECUTED",
    "PHYSICAL_SANITY_PASSED",
    "NUMERICALLY_CONVERGED",
    "CROSS_VALIDATED",
    "MEASUREMENT_CORRELATED",
    "PHYSICS_VERIFIED",
    "FABRICATION_SIGNED_OFF",
]

PUBLIC_DOCS = [
    "README.md",
    "ARCHITECTURE.md",
    "PROJECT_STATUS.md",
    "docker/README.md",
    "simulation/README.md",
]

CLAIM_TOKENS = (
    "supported",
    "verified",
    "executed",
    "validated",
    "passed",
    "pass",
    "works",
    "ready",
    "solver",
    "docker",
    "image",
    "sbom",
    "converged",
    "convergence",
    "physics",
    "fabrication",
    "level",
)

COMMAND_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class CommandResult:
    command: str
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "duration_seconds": round(self.duration_seconds, 3),
        }


def run(command: str, timeout: int = COMMAND_TIMEOUT_SECONDS) -> CommandResult:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return CommandResult(
            command=command,
            return_code=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            timed_out=False,
            duration_seconds=time.monotonic() - start,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            return_code=None,
            stdout=(exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            timed_out=True,
            duration_seconds=time.monotonic() - start,
        )


def read_toml(relative: str) -> dict[str, Any]:
    path = REPO / relative
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_write(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def maybe_json(command: str, timeout: int = COMMAND_TIMEOUT_SECONDS) -> Any:
    result = run(command, timeout=timeout)
    if result.return_code != 0 or not result.stdout:
        return result.to_dict()
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.to_dict()


def memory_snapshot() -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {
            "source": "python",
            "note": "available RAM not queried on non-Windows host",
        }
    command = (
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_ComputerSystem | "
        "Select-Object TotalPhysicalMemory,NumberOfLogicalProcessors,NumberOfProcessors | "
        "ConvertTo-Json -Compress\""
    )
    return {"source": "Win32_ComputerSystem", "payload": maybe_json(command)}


def disk_snapshot() -> dict[str, Any]:
    roots = sorted({REPO.anchor, str(REPO.drive + "\\") if REPO.drive else REPO.anchor})
    disks: dict[str, Any] = {}
    for root in roots:
        try:
            usage = shutil.disk_usage(root)
        except OSError as exc:
            disks[root] = {"error": str(exc)}
            continue
        disks[root] = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    return disks


def active_solver_processes() -> list[dict[str, Any]]:
    if platform.system().lower() != "windows":
        result = run("ps -eo pid,comm,args")
        names = ("palace", "openems", "fastercap", "fasthenry", "josim", "julia", "klayout")
        lines = [
            line
            for line in result.stdout.splitlines()
            if any(name in line.lower() for name in names)
        ]
        return [{"raw": line} for line in lines]
    command = (
        "powershell -NoProfile -Command "
        "\"Get-Process | Where-Object { "
        "$_.ProcessName -match 'palace|openems|fastercap|fasthenry|josim|julia|klayout|docker|mpiexec|mpirun|pvpython' "
        "} | Select-Object Id,ProcessName,Path,CPU,WorkingSet64 | ConvertTo-Json -Compress\""
    )
    payload = maybe_json(command)
    if isinstance(payload, dict) and "Id" in payload:
        return [payload]
    if isinstance(payload, list):
        return payload
    return [{"payload": payload}]


def command_available(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    if platform.system().lower() == "windows":
        return shutil.which(f"{name}.exe")
    return None


def tool_inventory() -> dict[str, Any]:
    registry = read_toml("external_tools/registry.toml")
    lock = read_toml("external_tools/lock.toml")
    locked = {tool["id"]: tool for tool in lock.get("locked_tools", [])}
    tools: list[dict[str, Any]] = []
    for tool in registry.get("tools", []):
        smoke = tool.get("smoke_test_command") or []
        executable = smoke[0] if smoke else tool["id"]
        executable_path = command_available(executable)
        smoke_result = None
        if executable_path and smoke:
            quoted = " ".join(subprocess.list2cmdline([str(part)]) for part in smoke)
            smoke_result = run(quoted, timeout=30).to_dict()
        tools.append(
            {
                "id": tool["id"],
                "canonical_name": tool.get("canonical_name"),
                "pinned_ref": tool.get("pinned_ref"),
                "pinned_commit": tool.get("pinned_commit"),
                "spdx_license": tool.get("spdx_license"),
                "install_mode": tool.get("install_mode"),
                "integration_mode": tool.get("integration_mode"),
                "registry_archive_sha256": tool.get("source_archive_sha256"),
                "lock_archive_sha256": locked.get(tool["id"], {}).get("source_archive_sha256"),
                "lock_checksum_verified": locked.get(tool["id"], {}).get("checksum_verified"),
                "redistribute_source": tool.get("redistribute_source"),
                "redistribute_binaries": tool.get("redistribute_binaries"),
                "executable_probe": executable,
                "executable_path": executable_path,
                "smoke_result": smoke_result,
                "current_state": "UPSTREAM_SMOKE_PASSED"
                if smoke_result and smoke_result["return_code"] == 0
                else "IMPLEMENTED"
                if tool.get("adapter_module") or locked.get(tool["id"])
                else "NOT_IMPLEMENTED",
                "state_note": "smoke ran locally"
                if smoke_result and smoke_result["return_code"] == 0
                else "registered and locked, but executable not proven locally",
            }
        )

    docker_commands = {
        "docker_version": run("docker --version", timeout=30).to_dict(),
        "docker_info": run("docker info --format \"{{json .}}\"", timeout=30).to_dict(),
        "docker_ps": run("docker ps", timeout=30).to_dict(),
        "podman_version": run("podman --version", timeout=30).to_dict(),
    }
    return {
        "schema": "textlayout.audit.tool-inventory.v1",
        "generated_at_epoch": int(time.time()),
        "registry": {
            "path": "external_tools/registry.toml",
            "sha256": sha256_file(REPO / "external_tools" / "registry.toml"),
            "tool_count": len(registry.get("tools", [])),
        },
        "lock": {
            "path": "external_tools/lock.toml",
            "sha256": sha256_file(REPO / "external_tools" / "lock.toml"),
            "tool_count": len(lock.get("locked_tools", [])),
        },
        "tools": tools,
        "container_runtime": docker_commands,
        "active_solver_processes": active_solver_processes(),
    }


def baseline(tool_payload: dict[str, Any]) -> dict[str, Any]:
    python = subprocess.list2cmdline([sys.executable])
    commands = [
        "git branch --show-current",
        "git rev-parse HEAD",
        "git rev-parse origin/main",
        "git status --short",
        "git show --no-patch --format=%P HEAD",
        "git log --oneline --decorate -20",
        "git log --oneline origin/main..HEAD",
        "git diff --stat origin/main...HEAD",
        f"{python} -m ruff check .",
        f"{python} -m mypy src/textlayout",
        f"{python} -m compileall src scripts examples",
    ]
    command_results = {command: run(command).to_dict() for command in commands}
    return {
        "schema": "textlayout.audit.baseline.v1",
        "generated_at_epoch": int(time.time()),
        "declared_start_commit": START_COMMIT,
        "pre_edit_observation": {
            "branch": "main",
            "local_head": START_COMMIT,
            "remote_head": START_COMMIT,
            "worktree_state": "clean",
            "recorded_before_file_edits": True,
            "note": (
                "Captured before creating the codex/mature-open-cqed-platform "
                "branch and before modifying files."
            ),
        },
        "repository": {
            "root": str(REPO),
            "branch": command_results["git branch --show-current"]["stdout"],
            "local_head": command_results["git rev-parse HEAD"]["stdout"],
            "remote_head": command_results["git rev-parse origin/main"]["stdout"],
            "worktree_state": command_results["git status --short"]["stdout"],
            "parent_commits": command_results["git show --no-patch --format=%P HEAD"][
                "stdout"
            ].split(),
        },
        "environment": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": sys.version,
            "python_executable": sys.executable,
            "memory": memory_snapshot(),
            "disk": disk_snapshot(),
        },
        "commands": command_results,
        "tool_inventory_summary": {
            "registered_tools": tool_payload["registry"]["tool_count"],
            "locked_tools": tool_payload["lock"]["tool_count"],
            "local_smokes_passed": [
                tool["id"]
                for tool in tool_payload["tools"]
                if tool["current_state"] == "UPSTREAM_SMOKE_PASSED"
            ],
            "active_solver_processes": tool_payload["active_solver_processes"],
        },
    }


def test_files_matching(*tokens: str) -> list[str]:
    matches: list[str] = []
    tests = REPO / "tests"
    for path in tests.rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if any(token.lower() in rel.lower() for token in tokens):
            matches.append(rel)
    return sorted(matches)


def capability_matrix(tool_payload: dict[str, Any]) -> dict[str, Any]:
    dockerfiles = sorted(path.relative_to(REPO).as_posix() for path in (REPO / "docker").glob("*.Dockerfile"))
    local_smoked = {
        tool["id"]
        for tool in tool_payload["tools"]
        if tool["current_state"] == "UPSTREAM_SMOKE_PASSED"
    }
    docker_available = (
        tool_payload["container_runtime"]["docker_ps"]["return_code"] == 0
        if isinstance(tool_payload["container_runtime"].get("docker_ps"), dict)
        else False
    )
    capabilities = [
        {
            "capability": "textlayout core CLI and typed workflow",
            "current_verification_level": "UNIT_TESTED",
            "evidence": [
                "src/textlayout/workflow/",
                "tests/textlayout_suite/test_workflow_graph.py",
                "ruff/mypy/compileall baseline commands",
            ],
            "missing_gates": [
                "fresh wheel install",
                "fresh container execution",
                "end-to-end real solver vertical slice",
            ],
        },
        {
            "capability": "CanonicalEvidence status semantics",
            "current_verification_level": "UNIT_TESTED",
            "evidence": [
                "src/textlayout/evidence/canonical.py",
                "tests/textlayout_suite/test_canonical_evidence.py",
                "tests/textlayout_suite/test_evidence_contract.py",
            ],
            "missing_gates": [
                "split historical solver execution and evidence generation provenance",
                "fresh-environment mutation guard for historical metadata",
            ],
        },
        {
            "capability": "external tool registry and lock metadata",
            "current_verification_level": "UNIT_TESTED",
            "evidence": [
                "external_tools/registry.toml",
                "external_tools/lock.toml",
                "tests/textlayout_suite/test_external_tool_registry.py",
                "scripts/external/check.py",
            ],
            "missing_gates": [
                "real source download in this run",
                "image build identity checks",
                "upstream smoke for every registered tool",
            ],
        },
        {
            "capability": "OCI solver stack",
            "current_verification_level": "IMPLEMENTED",
            "evidence": [
                "compose.yaml",
                "docker-bake.hcl",
                ".dockerignore",
                *dockerfiles,
                "tests/textlayout_suite/test_oci_stack.py",
            ],
            "missing_gates": [
                "Docker daemon available",
                "docker build",
                "docker run",
                "docker compose run",
                "real executable installation in solver images",
                "Syft-derived SBOM",
                "Trivy or Grype scan",
            ],
            "blocked_by": [] if docker_available else ["Docker daemon unavailable"],
        },
        {
            "capability": "Palace parser, retention, MAC, and vertical-slice scaffolding",
            "current_verification_level": "REAL_FIXTURE_TESTED",
            "evidence": test_files_matching("palace")[:30],
            "missing_gates": [
                "functional Palace executable/image in current environment",
                "bounded Palace benchmark executed",
                "quadrature-order convergence on fresh data",
                "field-energy reconstruction tolerance against Palace-owned CSV",
            ],
        },
        {
            "capability": "critical-region coverage modeling",
            "current_verification_level": "UNIT_TESTED",
            "evidence": [
                "src/textlayout/solvers/palace/models.py",
                "tests/textlayout_suite/test_palace_benchmark_v017.py",
                "tests/textlayout_suite/test_palace_benchmark_evidence.py",
            ],
            "missing_gates": [
                "declaration/entity/projection coverage separated for all requested regions",
                "negative tests for every malformed region case",
                "100% field projection coverage on real Palace field output",
            ],
        },
        {
            "capability": "KLayout DRC/readback",
            "current_verification_level": "UNIT_TESTED",
            "evidence": [
                "src/textlayout/verification/",
                "tests/textlayout_suite/test_verification.py",
            ],
            "missing_gates": [
                "headless KLayout image executes",
                "partial LVS report with unsupported-structure coverage",
                "real DRC/LVS runsets from typed PDK",
            ],
        },
        {
            "capability": "JosephsonCircuits nonlinear JPA execution",
            "current_verification_level": "IMPLEMENTED"
            if "josephsoncircuits" not in local_smoked
            else "UPSTREAM_SMOKE_PASSED",
            "evidence": [
                "external_tools/julia/JosephsonCircuits/Project.toml",
                "external_tools/julia/JosephsonCircuits/Manifest.toml",
                "src/textlayout/solvers/josephsoncircuits.py",
            ],
            "missing_gates": [
                "Julia executable available",
                "nonlinear harmonic-balance benchmark run",
                "pump/signal/idler/gain/bandwidth convergence",
            ],
        },
        {
            "capability": "openEMS resonator path",
            "current_verification_level": "REAL_FIXTURE_TESTED",
            "evidence": [
                "src/textlayout/simulation/openems_evidence.py",
                "tests/textlayout_suite/test_openems_evidence.py",
                "tests/textlayout_suite/test_touchstone_honesty.py",
            ],
            "missing_gates": [
                "real finite openEMS benchmark",
                "nonzero incident energy",
                "mesh/time/domain convergence",
                "port orientation and de-embedding provenance",
            ],
        },
        {
            "capability": "FasterCap and FastHenry extraction",
            "current_verification_level": "UNIT_TESTED",
            "evidence": [
                "src/textlayout/simulation/fastercap.py",
                "simulation/idc_fastercap/",
                "simulation/spiral_fasthenry/",
            ],
            "missing_gates": [
                "panel/filament refinement sequences",
                "matrix conservation/symmetry/PSD checks",
                "independent open-source or analytical comparison",
            ],
        },
        {
            "capability": "showcase evidence records",
            "current_verification_level": "UNIT_TESTED",
            "evidence": [
                "examples/showcase/*/evidence/canonical.json",
                "tests/textlayout_suite/test_showcase_examples.py",
                "scripts/audit_evidence_consistency.py",
            ],
            "missing_gates": [
                "fresh regeneration without historical solver metadata mutation",
                "real external reruns for current environment",
                "fabrication signoff",
            ],
        },
    ]
    return {
        "schema": "textlayout.audit.capability-matrix.v1",
        "generated_at_epoch": int(time.time()),
        "verification_ladder": VERIFICATION_LADDER,
        "capabilities": capabilities,
    }


def classify_claim(text: str) -> tuple[str, list[str], bool]:
    lower = text.lower()
    missing: list[str] = []
    downgrade = False
    if "physics_verified" in lower or "physics verified" in lower:
        level = "UNIT_TESTED"
        missing = [
            "fresh solver execution in this environment",
            "solver executable hash or container digest for all records",
            "independent reference and convergence audit per claim",
        ]
        if "currently exists" in lower or "artifacts are" in lower:
            downgrade = False
    elif "docker" in lower or "image" in lower or "sbom" in lower:
        level = "IMPLEMENTED"
        missing = [
            "docker daemon build/run",
            "real executable identity check",
            "filesystem-derived SBOM",
            "vulnerability scan",
        ]
        downgrade = "functional" in lower or "reproducible" in lower
    elif "executed" in lower or "solver" in lower:
        level = "UNIT_TESTED"
        missing = [
            "local external executable availability",
            "fresh upstream smoke",
            "fresh integration benchmark",
        ]
    elif "supported" in lower or "validated" in lower or "passed" in lower:
        level = "IMPLEMENTED"
        missing = ["fresh-environment validation", "external-tool execution where applicable"]
    else:
        level = "IMPLEMENTED"
        missing = ["manual audit if this is intended as a public capability claim"]
    return level, missing, downgrade


def claim_audit() -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for relative in PUBLIC_DOCS:
        path = REPO / relative
        if not path.is_file():
            claims.append(
                {
                    "source_file": relative,
                    "line": None,
                    "claim_text": "missing public document",
                    "supporting_evidence": [],
                    "current_verification_level": "NOT_IMPLEMENTED",
                    "missing_gates": ["create or remove reference to missing public document"],
                    "downgrade_required": True,
                }
            )
            continue
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            text = raw_line.strip()
            if not text or text.startswith("<!--"):
                continue
            lower = text.lower()
            if not any(token in lower for token in CLAIM_TOKENS):
                continue
            level, missing, downgrade = classify_claim(text)
            evidence: list[str] = []
            if "README.md" in relative:
                evidence.extend(
                    [
                        "scripts/validate_readme_claims.py",
                        "tests/textlayout_suite/test_readme_claims.py",
                    ]
                )
            if "PROJECT_STATUS" in relative:
                evidence.extend(["scripts/generate_project_status.py", "out/evidence/project_status.json"])
            if "docker" in lower or "image" in lower:
                evidence.extend(["compose.yaml", "docker-bake.hcl", "tests/textlayout_suite/test_oci_stack.py"])
            if "physics_verified" in lower or "physics verified" in lower:
                evidence.extend(["examples/showcase/*/evidence/canonical.json", "tests/textlayout_suite/test_showcase_examples.py"])
            claims.append(
                {
                    "source_file": relative,
                    "line": line_number,
                    "claim_text": text,
                    "supporting_evidence": sorted(set(evidence)),
                    "current_verification_level": level,
                    "missing_gates": missing,
                    "downgrade_required": downgrade,
                }
            )
    return {
        "schema": "textlayout.audit.claim-audit.v1",
        "generated_at_epoch": int(time.time()),
        "audit_scope": {
            "documents": PUBLIC_DOCS,
            "claim_detection": "non-empty public-doc lines containing conservative claim/status tokens",
        },
        "claims": claims,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output audit directory")
    args = parser.parse_args()

    out_dir = Path(args.out)
    tools = tool_inventory()
    json_write(out_dir / "tool_inventory.json", tools)
    json_write(out_dir / "baseline.json", baseline(tools))
    json_write(out_dir / "capability_matrix.json", capability_matrix(tools))
    json_write(out_dir / "claim_audit.json", claim_audit())
    print(f"wrote audit artifacts to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
