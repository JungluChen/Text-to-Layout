"""Generate machine-readable audit artifacts for Text-to-Layout.

The audit is deliberately conservative:

* ``manifest.json`` is deterministic for identical repository content.
* ``run.json`` contains host/run observations and is not meant to be committed.
* external tool states follow the release ladder and never promote registry
  metadata to installed/executed evidence.
* public claims are evaluated against typed evidence rules, not keywords alone.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "out" / "audit"

TOOL_STATE_LADDER = [
    "UNREGISTERED",
    "REGISTERED",
    "LOCKED",
    "SOURCE_DOWNLOADED",
    "CHECKSUM_VERIFIED",
    "LICENSE_REVIEWED",
    "INSTALLED",
    "IDENTITY_VERIFIED",
    "UPSTREAM_SMOKE_PASSED",
    "INTEGRATION_TEST_PASSED",
    "BENCHMARK_EXECUTED",
    "NUMERICALLY_VALIDATED",
    "SCIENTIFICALLY_VALIDATED",
    "DISABLED_REFERENCE_ONLY",
]

CAPABILITY_LEVELS = [
    "NOT_IMPLEMENTED",
    "IMPLEMENTED",
    "UNIT_TESTED",
    "REAL_FIXTURE_TESTED",
    "FRESH_ENVIRONMENT_TESTED",
    "UPSTREAM_SMOKE_PASSED",
    "INTEGRATION_TEST_PASSED",
    "BENCHMARK_EXECUTED",
    "NUMERICALLY_VALIDATED",
    "SCIENTIFICALLY_VALIDATED",
]

PUBLIC_DOCS = [
    "README.md",
    "ARCHITECTURE.md",
    "PROJECT_STATUS.md",
    "docker/README.md",
    "simulation/README.md",
]

MANIFEST_FILES = [
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "ARCHITECTURE.md",
    "PROJECT_STATUS.md",
    "THIRD_PARTY_NOTICES.md",
    "external_tools/registry.toml",
    "external_tools/lock.toml",
    "compose.yaml",
    "docker-bake.hcl",
    ".dockerignore",
]

CLAIM_TOKENS = (
    "supported",
    "verified",
    "executed",
    "validated",
    "passed",
    "pass",
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

PYTHON_PACKAGE_TOOLS = {
    "gmsh": ("gmsh", "gmsh"),
    "josephsoncircuits": ("JosephsonCircuits", "JosephsonCircuits"),
    "kqcircuits": ("kqcircuits", "kqcircuits"),
    "qiskit-metal": ("qiskit_metal", "qiskit-metal"),
    "scqubits": ("scqubits", "scqubits"),
    "squadds": ("squadds", "squadds"),
}

COMMAND_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float

    def to_run_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "return_code": self.return_code,
            "stdout": redact(self.stdout),
            "stderr": redact(self.stderr),
            "stdout_sha256": sha256_text(self.stdout),
            "stderr_sha256": sha256_text(self.stderr),
            "timed_out": self.timed_out,
            "duration_seconds": round(self.duration_seconds, 3),
        }

    def to_probe_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "return_code": self.return_code,
            "stdout_sha256": sha256_text(self.stdout),
            "stderr_sha256": sha256_text(self.stderr),
            "timed_out": self.timed_out,
        }


@dataclass(frozen=True)
class Gate:
    name: str
    level: str
    passed: bool
    evidence_paths: tuple[str, ...] = ()
    reason: str | None = None
    blocked: bool = False


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_toml(relative: str) -> dict[str, Any]:
    path = REPO / relative
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def stable_label(value: str, prefix: str) -> str:
    return f"${prefix}:{sha256_text(value)[:16]}"


def relative_path(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def normalize_path(value: str) -> str:
    path = Path(value)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        return resolved.relative_to(REPO).as_posix()
    except ValueError:
        pass
    home = Path.home()
    try:
        home_relative = resolved.relative_to(home)
        return f"$HOME/{home_relative.as_posix()}"
    except ValueError:
        return stable_label(str(resolved), "ABS_PATH")


def redact_string(value: str) -> str:
    redacted = value
    repo_variants = {str(REPO), str(REPO.resolve())}
    home_variants = {str(Path.home()), str(Path.home().resolve())}
    for repo in sorted(repo_variants, key=len, reverse=True):
        redacted = redacted.replace(repo, "$REPO")
        redacted = redacted.replace(repo.replace("\\", "\\\\"), "$REPO")
    for home in sorted(home_variants, key=len, reverse=True):
        redacted = redacted.replace(home, "$HOME")
        redacted = redacted.replace(home.replace("\\", "\\\\"), "$HOME")

    # Replace remaining absolute Windows paths, including Docker plugin paths.
    def _windows_path(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith("$REPO") or token.startswith("$HOME"):
            return token
        return stable_label(token, "ABS_PATH")

    redacted = re.sub(r"(?<![$\w])(?:[A-Za-z]:\\\\|[A-Za-z]:\\)[^\"'\s,;}]+", _windows_path, redacted)
    return redacted


def redact(payload: Any) -> Any:
    if isinstance(payload, str):
        return redact_string(payload)
    if isinstance(payload, list):
        return [redact(item) for item in payload]
    if isinstance(payload, dict):
        return {str(key): redact(value) for key, value in payload.items()}
    return payload


def json_write(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(args: list[str], timeout: int = COMMAND_TIMEOUT_SECONDS) -> CommandResult:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=REPO,
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return CommandResult(
            command=args,
            return_code=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            timed_out=False,
            duration_seconds=time.monotonic() - start,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        stdout = getattr(exc, "stdout", "") or ""
        stderr = getattr(exc, "stderr", "") or str(exc)
        return CommandResult(
            command=args,
            return_code=None,
            stdout=stdout if isinstance(stdout, str) else "",
            stderr=stderr if isinstance(stderr, str) else str(stderr),
            timed_out=isinstance(exc, subprocess.TimeoutExpired),
            duration_seconds=time.monotonic() - start,
        )


def git_stdout(*args: str) -> str:
    result = run_command(["git", *args], timeout=60)
    if result.return_code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout


def repository_observation(expected_start_commit: str | None = None) -> dict[str, Any]:
    head = git_stdout("rev-parse", "HEAD")
    remote = run_command(["git", "rev-parse", "origin/main"], timeout=60)
    parents = git_stdout("show", "--no-patch", "--format=%P", "HEAD").split()
    observation = {
        "branch": git_stdout("branch", "--show-current"),
        "local_head": head,
        "remote_head": remote.stdout if remote.return_code == 0 else None,
        "remote_head_error": remote.stderr if remote.return_code != 0 else None,
        "worktree_state": git_stdout("status", "--short"),
        "parent_commits": parents,
        "collection_timestamp_epoch": int(time.time()),
        "expected_start_commit": expected_start_commit,
        "expected_start_valid": None,
        "expected_start_error": None,
    }
    if expected_start_commit:
        exact = head == expected_start_commit
        ancestor = run_command(
            ["git", "merge-base", "--is-ancestor", expected_start_commit, "HEAD"],
            timeout=60,
        )
        observation["expected_start_valid"] = exact or ancestor.return_code == 0
        if not observation["expected_start_valid"]:
            observation["expected_start_error"] = (
                f"HEAD {head} is neither {expected_start_commit} nor a direct descendant"
            )
    return observation


def deterministic_file_manifest() -> list[dict[str, Any]]:
    files: set[str] = set(MANIFEST_FILES)
    files.update(relative_path(path) for path in (REPO / "docker").glob("*.Dockerfile"))
    files.update(relative_path(path) for path in (REPO / ".github" / "workflows").glob("*.yml"))
    files.update(
        relative_path(path)
        for path in (REPO / "examples" / "showcase").glob("*/evidence/canonical.json")
    )
    rows: list[dict[str, Any]] = []
    for relative in sorted(files):
        path = REPO / relative
        rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size if path.is_file() else None,
            }
        )
    return rows


def deterministic_manifest(repository: dict[str, Any]) -> dict[str, Any]:
    registry = read_toml("external_tools/registry.toml")
    lock = read_toml("external_tools/lock.toml")
    return {
        "schema": "textlayout.audit.manifest.v1",
        "source_revision": repository["local_head"],
        "parent_commits": repository["parent_commits"],
        "repository_files": deterministic_file_manifest(),
        "external_tools": deterministic_tool_manifest(registry, lock),
    }


def deterministic_tool_manifest(
    registry: dict[str, Any], lock: dict[str, Any]
) -> list[dict[str, Any]]:
    locked = {tool["id"]: tool for tool in lock.get("locked_tools", [])}
    rows = []
    for tool in sorted(registry.get("tools", []), key=lambda item: item["id"]):
        lock_row = locked.get(tool["id"], {})
        rows.append(
            {
                "id": tool["id"],
                "canonical_name": tool.get("canonical_name"),
                "pinned_ref": tool.get("pinned_ref"),
                "pinned_commit": tool.get("pinned_commit"),
                "spdx_license": tool.get("spdx_license"),
                "license_review": tool.get("license_review"),
                "resolved_commit": lock_row.get("resolved_commit"),
                "source_archive_sha256": tool.get("source_archive_sha256"),
                "lock_archive_sha256": lock_row.get("source_archive_sha256"),
                "checksum_verified": lock_row.get("checksum_verified"),
                "redistribute_source": tool.get("redistribute_source"),
                "redistribute_binaries": tool.get("redistribute_binaries"),
                "adapter_module": tool.get("adapter_module"),
            }
        )
    return rows


def memory_snapshot() -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"source": "not_collected", "reason": "non-Windows host"}
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-CimInstance Win32_ComputerSystem | "
            "Select-Object TotalPhysicalMemory,NumberOfLogicalProcessors,NumberOfProcessors | "
            "ConvertTo-Json -Compress"
        ),
    ]
    result = run_command(command, timeout=30)
    try:
        payload: Any = json.loads(result.stdout) if result.return_code == 0 else None
    except json.JSONDecodeError:
        payload = result.to_run_dict()
    return {"source": "Win32_ComputerSystem", "payload": redact(payload)}


def disk_snapshot() -> dict[str, Any]:
    roots = sorted({REPO.anchor, str(REPO.drive + "\\") if REPO.drive else REPO.anchor})
    disks: dict[str, Any] = {}
    for root in roots:
        try:
            usage = shutil.disk_usage(root)
        except OSError as exc:
            disks[normalize_path(root)] = {"error": str(exc)}
            continue
        disks[normalize_path(root)] = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    return disks


def docker_commands() -> dict[str, Any]:
    commands = {
        "docker_version": ["docker", "version"],
        "docker_info": ["docker", "info"],
        "docker_context_show": ["docker", "context", "show"],
        "docker_buildx_ls": ["docker", "buildx", "ls"],
        "docker_compose_version": ["docker", "compose", "version"],
        "docker_ps": ["docker", "ps"],
        "podman_version": ["podman", "--version"],
    }
    return {
        name: run_command(command, timeout=30).to_run_dict()
        for name, command in sorted(commands.items())
    }


def active_solver_processes() -> list[dict[str, Any]]:
    if platform.system().lower() != "windows":
        result = run_command(["ps", "-eo", "pid,comm,args"], timeout=30)
        names = ("palace", "openems", "fastercap", "fasthenry", "josim", "julia", "klayout")
        return [
            {"raw": redact(line)}
            for line in result.stdout.splitlines()
            if any(name in line.lower() for name in names)
        ]
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-Process | Where-Object { "
            "$_.ProcessName -match 'palace|openems|fastercap|fasthenry|josim|julia|"
            "klayout|docker|mpiexec|mpirun|pvpython' } | "
            "Select-Object Id,ProcessName,Path,CPU,WorkingSet64 | ConvertTo-Json -Compress"
        ),
    ]
    result = run_command(command, timeout=30)
    if result.return_code != 0 or not result.stdout:
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [{"raw": redact(result.stdout)}]
    if isinstance(payload, dict):
        payload = [payload]
    return redact(payload)


def run_record(repository: dict[str, Any]) -> dict[str, Any]:
    python = sys.executable
    commands = {
        "ruff": [python, "-m", "ruff", "check", "."],
        "mypy": [python, "-m", "mypy", "src/textlayout"],
        "compileall": [python, "-m", "compileall", "-q", "src", "scripts", "examples"],
    }
    return {
        "schema": "textlayout.audit.run.v1",
        "repository": redact(repository),
        "host": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": sys.version,
            "python_executable": normalize_path(sys.executable),
            "python_executable_sha256": sha256_file(Path(sys.executable)),
            "virtual_environment": virtual_environment_identity(),
            "memory": memory_snapshot(),
            "disk": disk_snapshot(),
        },
        "commands": {
            name: run_command(command, timeout=COMMAND_TIMEOUT_SECONDS).to_run_dict()
            for name, command in commands.items()
        },
        "container_runtime": docker_commands(),
        "active_solver_processes": active_solver_processes(),
    }


def virtual_environment_identity() -> dict[str, Any]:
    prefix = Path(sys.prefix)
    base = Path(getattr(sys, "base_prefix", sys.prefix))
    return {
        "is_venv": prefix != base,
        "prefix": normalize_path(str(prefix)),
        "base_prefix": normalize_path(str(base)),
        "pyvenv_cfg_sha256": sha256_file(prefix / "pyvenv.cfg"),
    }


def command_available(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    if platform.system().lower() == "windows":
        return shutil.which(f"{name}.exe")
    return None


def probe_python_package(import_name: str, distribution_name: str) -> dict[str, Any]:
    executable = Path(sys.executable)
    spec = importlib.util.find_spec(import_name)
    version: str | None
    try:
        version = importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        version = None
    package_root = None
    if spec is not None:
        origin = spec.origin or ""
        if origin and origin not in {"built-in", "namespace"}:
            package_root = normalize_path(str(Path(origin).parent))
    code = (
        "import importlib, json; "
        f"module=importlib.import_module({import_name!r}); "
        "print(json.dumps({'module': module.__name__}))"
    )
    result = run_command([str(executable), "-c", code], timeout=30)
    return {
        "active_python_executable": normalize_path(str(executable)),
        "active_python_executable_sha256": sha256_file(executable),
        "virtual_environment": virtual_environment_identity(),
        "package_name": import_name,
        "distribution_name": distribution_name,
        "distribution_version": version,
        "package_root": package_root,
        "import_return_code": result.return_code,
        "import_stdout_sha256": sha256_text(result.stdout),
        "import_stderr_sha256": sha256_text(result.stderr),
        "present": spec is not None and result.return_code == 0,
    }


def is_identity_probe(command: list[str]) -> bool:
    joined = " ".join(command).lower()
    return any(token in joined for token in ("--version", " -v", " version", "pkgversion"))


def state_index(state: str) -> int:
    return TOOL_STATE_LADDER.index(state)


def max_state(*states: str) -> str:
    return max(states, key=state_index)


def external_tool_state(
    tool: dict[str, Any],
    locked: dict[str, Any],
    package_probe: dict[str, Any] | None,
    executable_path: str | None,
    smoke_result: CommandResult | None,
) -> tuple[str, list[str]]:
    tool_id = tool["id"]
    if tool_id == "pyepr":
        return "DISABLED_REFERENCE_ONLY", ["disabled commercial-HFSS reference path only"]
    state = "REGISTERED"
    notes = ["registry entry exists"]
    lock_row = locked.get(tool_id)
    if lock_row:
        state = max_state(state, "LOCKED")
        notes.append("lock entry exists")
        if lock_row.get("checksum_verified"):
            state = max_state(state, "CHECKSUM_VERIFIED")
            notes.append("locked checksum marked verified")
    if tool.get("license_review"):
        state = max_state(state, "LICENSE_REVIEWED")
        notes.append("license review recorded")
    if package_probe and package_probe.get("present"):
        state = max_state(state, "IDENTITY_VERIFIED")
        notes.append("package import succeeded in active interpreter")
    elif executable_path:
        state = max_state(state, "INSTALLED")
        notes.append("executable found on PATH")
    if executable_path and smoke_result and smoke_result.return_code == 0:
        if is_identity_probe(smoke_result.command):
            state = max_state(state, "IDENTITY_VERIFIED")
            notes.append("identity/version probe succeeded")
        else:
            state = max_state(state, "UPSTREAM_SMOKE_PASSED")
            notes.append("upstream smoke command succeeded")
    return state, notes


def tool_inventory() -> dict[str, Any]:
    registry = read_toml("external_tools/registry.toml")
    lock = read_toml("external_tools/lock.toml")
    locked = {tool["id"]: tool for tool in lock.get("locked_tools", [])}
    rows: list[dict[str, Any]] = []
    for tool in sorted(registry.get("tools", []), key=lambda item: item["id"]):
        tool_id = tool["id"]
        package_probe = None
        if tool_id in PYTHON_PACKAGE_TOOLS:
            import_name, distribution_name = PYTHON_PACKAGE_TOOLS[tool_id]
            package_probe = probe_python_package(import_name, distribution_name)
        smoke = [str(part) for part in tool.get("smoke_test_command") or []]
        executable = smoke[0] if smoke else tool_id
        executable_path = command_available(executable)
        smoke_result = None
        if executable_path and smoke and tool_id not in PYTHON_PACKAGE_TOOLS:
            smoke_result = run_command(smoke, timeout=30)
        current_state, notes = external_tool_state(
            tool, locked, package_probe, executable_path, smoke_result
        )
        rows.append(
            {
                "id": tool_id,
                "canonical_name": tool.get("canonical_name"),
                "current_state": current_state,
                "state_notes": notes,
                "pinned_ref": tool.get("pinned_ref"),
                "pinned_commit": tool.get("pinned_commit"),
                "spdx_license": tool.get("spdx_license"),
                "license_review": tool.get("license_review"),
                "lock_checksum_verified": locked.get(tool_id, {}).get("checksum_verified"),
                "executable_probe": executable,
                "executable_path": normalize_path(executable_path) if executable_path else None,
                "smoke_result": smoke_result.to_probe_dict() if smoke_result else None,
                "python_package_probe": package_probe,
            }
        )
    return {
        "schema": "textlayout.audit.tool-inventory.v2",
        "tool_state_ladder": TOOL_STATE_LADDER,
        "evaluated_at_commit": git_stdout("rev-parse", "HEAD"),
        "tools": rows,
    }


def evidence_hashes(paths: list[str]) -> list[dict[str, Any]]:
    rows = []
    for relative in sorted(paths):
        path = REPO / relative
        rows.append({"path": relative, "sha256": sha256_file(path), "exists": path.exists()})
    return rows


def highest_capability_level(gates: list[Gate]) -> str:
    passed_levels = [gate.level for gate in gates if gate.passed]
    if not passed_levels:
        return "NOT_IMPLEMENTED"
    return max(passed_levels, key=CAPABILITY_LEVELS.index)


def capability_result(name: str, gates: list[Gate], commit: str) -> dict[str, Any]:
    evidence_paths = sorted({path for gate in gates for path in gate.evidence_paths})
    return {
        "capability": name,
        "computed_level": highest_capability_level(gates),
        "passed_gates": [gate.name for gate in gates if gate.passed],
        "failed_gates": [
            {"gate": gate.name, "reason": gate.reason}
            for gate in gates
            if not gate.passed and not gate.blocked
        ],
        "blocked_gates": [
            {"gate": gate.name, "reason": gate.reason}
            for gate in gates
            if not gate.passed and gate.blocked
        ],
        "evidence_hashes": evidence_hashes(evidence_paths),
        "evaluated_at_commit": commit,
    }


def path_exists(relative: str) -> bool:
    return (REPO / relative).exists()


def any_path(glob: str) -> bool:
    return any(REPO.glob(glob))


def capability_matrix(tool_payload: dict[str, Any], run_payload: dict[str, Any] | None) -> dict[str, Any]:
    commit = git_stdout("rev-parse", "HEAD")
    docker_ok = False
    if run_payload:
        docker_ps = run_payload.get("container_runtime", {}).get("docker_ps", {})
        docker_ok = docker_ps.get("return_code") == 0
    tool_states = {tool["id"]: tool["current_state"] for tool in tool_payload["tools"]}
    capabilities = [
        capability_result(
            "core wheel and CLI",
            [
                Gate("pyproject declares package", "IMPLEMENTED", path_exists("pyproject.toml"), ("pyproject.toml",)),
                Gate("core tests exist", "UNIT_TESTED", any_path("tests/textlayout_suite/test_workflow_graph.py"), ("tests/textlayout_suite/test_workflow_graph.py",)),
                Gate(
                    "fresh wheel install recorded",
                    "FRESH_ENVIRONMENT_TESTED",
                    path_exists("out/audit/core_install.json"),
                    ("out/audit/core_install.json",),
                ),
            ],
            commit,
        ),
        capability_result(
            "CanonicalEvidence semantics",
            [
                Gate("schema implemented", "IMPLEMENTED", path_exists("src/textlayout/evidence/canonical.py"), ("src/textlayout/evidence/canonical.py",)),
                Gate("schema unit tests exist", "UNIT_TESTED", path_exists("tests/textlayout_suite/test_canonical_evidence.py"), ("tests/textlayout_suite/test_canonical_evidence.py",)),
            ],
            commit,
        ),
        capability_result(
            "OCI stack",
            [
                Gate("docker configuration exists", "IMPLEMENTED", path_exists("compose.yaml") and path_exists("docker-bake.hcl"), ("compose.yaml", "docker-bake.hcl")),
                Gate("docker daemon available", "UPSTREAM_SMOKE_PASSED", docker_ok, reason="Docker daemon unavailable", blocked=not docker_ok),
                Gate("image build evidence exists", "INTEGRATION_TEST_PASSED", path_exists("out/audit/klayout_image.json"), ("out/audit/klayout_image.json",)),
            ],
            commit,
        ),
        capability_result(
            "Palace parser/MAC",
            [
                Gate("Palace parser implemented", "IMPLEMENTED", path_exists("src/textlayout/solvers/palace/parser.py"), ("src/textlayout/solvers/palace/parser.py",)),
                Gate("Palace fixture tests exist", "REAL_FIXTURE_TESTED", any_path("tests/fixtures/palace_0_17_*"), ("tests/textlayout_suite/test_palace_higher_order_vtk.py",)),
            ],
            commit,
        ),
        capability_result(
            "Palace real execution",
            [
                Gate("Palace registered", "IMPLEMENTED", "palace" in tool_states, ("external_tools/registry.toml",)),
                Gate("Palace upstream smoke passed", "UPSTREAM_SMOKE_PASSED", tool_states.get("palace") == "UPSTREAM_SMOKE_PASSED"),
                Gate("Palace benchmark evidence exists", "BENCHMARK_EXECUTED", path_exists("out/audit/palace_benchmark.json")),
            ],
            commit,
        ),
        capability_result(
            "critical-region coverage",
            [
                Gate("typed models implemented", "IMPLEMENTED", path_exists("src/textlayout/solvers/palace/models.py"), ("src/textlayout/solvers/palace/models.py",)),
                Gate("coverage tests exist", "UNIT_TESTED", path_exists("tests/textlayout_suite/test_palace_benchmark_v017.py"), ("tests/textlayout_suite/test_palace_benchmark_v017.py",)),
            ],
            commit,
        ),
        capability_result(
            "KLayout DRC",
            [
                Gate("KLayout adapter implemented", "IMPLEMENTED", path_exists("src/textlayout/verification/klayout.py"), ("src/textlayout/verification/klayout.py",)),
                Gate(
                    "KLayout identity verified",
                    "IMPLEMENTED",
                    tool_states.get("klayout") in {"IDENTITY_VERIFIED", "UPSTREAM_SMOKE_PASSED"},
                ),
                Gate("headless DRC integration evidence", "INTEGRATION_TEST_PASSED", path_exists("out/audit/klayout_drc.json")),
            ],
            commit,
        ),
        capability_result(
            "KLayout partial LVS",
            [
                Gate("LVS report schema implemented", "IMPLEMENTED", path_exists("src/textlayout/verification/report.py"), ("src/textlayout/verification/report.py",)),
                Gate("partial LVS evidence exists", "INTEGRATION_TEST_PASSED", path_exists("out/audit/klayout_lvs.json")),
            ],
            commit,
        ),
        capability_result(
            "JosephsonCircuits",
            [
                Gate("adapter implemented", "IMPLEMENTED", path_exists("src/textlayout/solvers/josephsoncircuits.py"), ("src/textlayout/solvers/josephsoncircuits.py",)),
                Gate(
                    "package identity verified",
                    "IMPLEMENTED",
                    tool_states.get("josephsoncircuits")
                    in {"IDENTITY_VERIFIED", "UPSTREAM_SMOKE_PASSED"},
                ),
                Gate("linear LC benchmark evidence", "INTEGRATION_TEST_PASSED", path_exists("out/audit/josephson_linear_lc.json")),
            ],
            commit,
        ),
        capability_result(
            "openEMS",
            [
                Gate("openEMS evidence parser implemented", "IMPLEMENTED", path_exists("src/textlayout/simulation/openems_evidence.py"), ("src/textlayout/simulation/openems_evidence.py",)),
                Gate("openEMS fixture tests exist", "REAL_FIXTURE_TESTED", path_exists("tests/textlayout_suite/test_openems_evidence.py"), ("tests/textlayout_suite/test_openems_evidence.py",)),
            ],
            commit,
        ),
        capability_result(
            "FasterCap",
            [
                Gate("FasterCap adapter implemented", "IMPLEMENTED", path_exists("src/textlayout/simulation/fastercap.py"), ("src/textlayout/simulation/fastercap.py",)),
                Gate("FasterCap real convergence evidence", "BENCHMARK_EXECUTED", path_exists("out/audit/fastercap_convergence.json")),
            ],
            commit,
        ),
        capability_result(
            "FastHenry",
            [
                Gate("FastHenry handoff exists", "IMPLEMENTED", path_exists("simulation/spiral_fasthenry/README.md"), ("simulation/spiral_fasthenry/README.md",)),
                Gate("FastHenry convergence evidence", "BENCHMARK_EXECUTED", path_exists("out/audit/fasthenry_convergence.json")),
            ],
            commit,
        ),
        capability_result(
            "showcase evidence",
            [
                Gate("canonical showcase evidence exists", "IMPLEMENTED", any_path("examples/showcase/*/evidence/canonical.json")),
                Gate("showcase consistency tests exist", "UNIT_TESTED", path_exists("tests/textlayout_suite/test_showcase_examples.py"), ("tests/textlayout_suite/test_showcase_examples.py",)),
            ],
            commit,
        ),
    ]
    return {
        "schema": "textlayout.audit.capability-matrix.v2",
        "capability_levels": CAPABILITY_LEVELS,
        "capabilities": capabilities,
    }


def load_canonical(relative: str) -> dict[str, Any] | None:
    path = REPO / relative
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("confidence_class", None)
    return payload


def finite(value: Any) -> bool:
    return isinstance(value, int | float) and math.isfinite(float(value))


def physics_evidence_level(record: dict[str, Any] | None) -> tuple[str, list[str], list[str]]:
    if record is None:
        return "NOT_IMPLEMENTED", [], ["canonical evidence missing"]
    passed: list[str] = []
    missing: list[str] = []
    if record.get("solver_executable_sha256") or record.get("container_digest"):
        passed.append("solver identity hash or container digest")
    else:
        missing.append("solver identity hash or immutable container digest")
    if record.get("return_code") == 0 and record.get("command") and record.get("output_file_hashes"):
        passed.append("actual solver execution")
    else:
        missing.append("actual solver execution")
    if finite(record.get("extracted_value")):
        passed.append("finite parsed output")
    else:
        missing.append("finite parsed output")
    checks = record.get("sanity_checks") or []
    if checks and all(check.get("passed") for check in checks):
        passed.append("physical sanity checks")
    else:
        missing.append("non-empty passing physical sanity checks")
    convergence = record.get("convergence") or {}
    if convergence.get("converged") is True:
        passed.append("independent numerical-convergence evidence")
    else:
        missing.append("independent numerical-convergence evidence")
    if record.get("measurement") or record.get("analytical_model") or record.get("depends_on"):
        passed.append("independent reference or measurement")
    else:
        missing.append("independent reference or measurement")
    if (
        record.get("solver_execution_environment_hash")
        and record.get("evidence_generation_environment_hash")
    ):
        passed.append("split execution/generation environment identity")
    else:
        missing.append("split execution/generation environment identity")

    if not missing:
        return "PHYSICS_VERIFIED", passed, missing
    if "independent numerical-convergence evidence" in passed:
        return "NUMERICALLY_CONVERGED", passed, missing
    if "finite parsed output" in passed:
        return "OUTPUT_PARSED", passed, missing
    if "actual solver execution" in passed:
        return "SOLVER_EXECUTED", passed, missing
    return "IMPLEMENTED", passed, missing


def claim_type_for(text: str) -> str:
    lower = text.lower()
    if "physics_verified" in lower or "physics verified" in lower:
        return "physics_verified"
    if "docker" in lower or "image" in lower or "sbom" in lower:
        return "oci"
    if "fabrication" in lower:
        return "fabrication"
    if "executed" in lower or "solver" in lower:
        return "solver_execution"
    if "supported" in lower or "validated" in lower or "passed" in lower:
        return "support"
    return "general"


def claim_subject(text: str) -> str:
    match = re.search(r"examples/showcase/([^/\s)]+)", text)
    if match:
        return match.group(1)
    ids = re.findall(r"`?(\d{2}_[A-Za-z0-9_]+)`?", text)
    if ids:
        return ",".join(ids)
    for token in ("IDC", "CPW", "KLayout", "JosephsonCircuits", "Palace", "openEMS"):
        if token.lower() in text.lower():
            return token
    return "project"


def linked_showcase_evidence(text: str) -> list[str]:
    paths = []
    ids = set(re.findall(r"examples/showcase/([^/\s)]+)", text))
    ids.update(re.findall(r"`(\d{2}_[A-Za-z0-9_]+)`", text))
    ids.update(re.findall(r"\b(\d{2}_[A-Za-z0-9_]+)\b", text))
    for showcase_id in sorted(ids):
        candidate = f"examples/showcase/{showcase_id}/evidence/canonical.json"
        if (REPO / candidate).is_file():
            paths.append(candidate)
    return paths


def evaluate_claim(text: str) -> tuple[str, list[str], list[str], str]:
    claim_type = claim_type_for(text)
    if claim_type == "physics_verified":
        evidence_paths = linked_showcase_evidence(text)
        if not evidence_paths:
            return (
                "NOT_IMPLEMENTED",
                [],
                ["PHYSICS_VERIFIED claim is not linked to canonical evidence"],
                "Replace PHYSICS_VERIFIED with the highest canonical status and link evidence.",
            )
        levels = []
        passed_all: list[str] = []
        missing_all: list[str] = []
        for path in evidence_paths:
            level, passed, missing = physics_evidence_level(load_canonical(path))
            levels.append(level)
            passed_all.extend(f"{path}: {item}" for item in passed)
            missing_all.extend(f"{path}: {item}" for item in missing)
        computed = min(levels, key=lambda level: CLAIM_LEVEL_ORDER.index(level))
        replacement = (
            f"Replace PHYSICS_VERIFIED with {computed}; keep target_tolerance_passed separate."
            if missing_all
            else "No replacement required."
        )
        return computed, passed_all, missing_all, replacement
    if claim_type == "oci":
        return (
            "IMPLEMENTED",
            ["Dockerfiles/Compose may exist"],
            ["docker build/run, executable identity, Syft SBOM, vulnerability scan"],
            "State OCI work as configured but not runtime-verified unless image evidence exists.",
        )
    if claim_type == "fabrication":
        return (
            "IMPLEMENTED",
            [],
            ["foundry-qualified DRC/LVS/fabrication signoff evidence"],
            "Use NOT_FABRICATION_READY unless foundry signoff evidence exists.",
        )
    if claim_type == "solver_execution":
        return (
            "IMPLEMENTED",
            [],
            ["fresh external solver execution in this environment"],
            "State solver execution as conditional or historical unless run evidence is linked.",
        )
    return (
        "IMPLEMENTED",
        [],
        ["typed evidence rule for this public claim"],
        "Keep claim conservative or link a machine-readable evidence record.",
    )


CLAIM_LEVEL_ORDER = [
    "NOT_IMPLEMENTED",
    "IMPLEMENTED",
    "SOLVER_EXECUTED",
    "OUTPUT_PARSED",
    "NUMERICALLY_CONVERGED",
    "PHYSICS_VERIFIED",
]


def claim_audit() -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for relative in PUBLIC_DOCS:
        path = REPO / relative
        if not path.is_file():
            claims.append(
                {
                    "claim_id": sha256_text(f"{relative}:missing")[:16],
                    "source_file": relative,
                    "line": 0,
                    "claim_type": "document_missing",
                    "subject": relative,
                    "claim_text": "public document missing",
                    "claimed_level": "NOT_IMPLEMENTED",
                    "linked_evidence": [],
                    "computed_level": "NOT_IMPLEMENTED",
                    "passed_gates": [],
                    "missing_mandatory_gates": ["document exists"],
                    "downgrade_required": True,
                    "suggested_replacement": "Create the document or remove references to it.",
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
            claim_type = claim_type_for(text)
            claimed = "PHYSICS_VERIFIED" if claim_type == "physics_verified" else "IMPLEMENTED"
            computed, passed, missing, replacement = evaluate_claim(text)
            claims.append(
                {
                    "claim_id": sha256_text(f"{relative}:{line_number}:{text}")[:16],
                    "source_file": relative,
                    "line": line_number,
                    "claim_type": claim_type,
                    "subject": claim_subject(text),
                    "claim_text": text,
                    "claimed_level": claimed,
                    "linked_evidence": linked_showcase_evidence(text),
                    "computed_level": computed,
                    "passed_gates": sorted(set(passed)),
                    "missing_mandatory_gates": sorted(set(missing)),
                    "downgrade_required": bool(missing) and CLAIM_LEVEL_ORDER.index(computed) < CLAIM_LEVEL_ORDER.index(claimed),
                    "suggested_replacement": replacement,
                }
            )
    return {
        "schema": "textlayout.audit.claim-audit.v2",
        "audit_scope": {
            "documents": PUBLIC_DOCS,
            "claim_detection": "typed rules over public-doc lines containing claim/status tokens",
        },
        "claims": claims,
    }


def run_core_install_gate(out_dir: Path) -> dict[str, Any]:
    dist_dir = REPO / "dist"
    build_result = run_command(["uv", "build"], timeout=300)
    wheels = sorted(dist_dir.glob("*.whl"))
    wheel = wheels[-1] if wheels else None
    with tempfile.TemporaryDirectory(prefix="textlayout-wheel-") as tmp:
        venv = Path(tmp) / "venv"
        venv_result = run_command(["uv", "venv", str(venv)], timeout=120)
        python = venv / ("Scripts/python.exe" if platform.system().lower() == "windows" else "bin/python")
        cli = venv / ("Scripts/textlayout.exe" if platform.system().lower() == "windows" else "bin/textlayout")
        install_result = (
            run_command(["uv", "pip", "install", "--python", str(python), str(wheel)], timeout=300)
            if wheel
            else CommandResult(["uv", "pip", "install"], 1, "", "no wheel produced", False, 0.0)
        )
        help_result = run_command([str(cli), "--help"], timeout=120) if cli.exists() else CommandResult([str(cli), "--help"], 1, "", "CLI missing", False, 0.0)
        workflow_out = out_dir / "core_workflow"
        workflow_result = run_command(
            [
                str(cli),
                "prompt",
                "Create a 0.6 pF IDC on silicon with 2 um min gap",
                "--out",
                str(workflow_out),
                "--no-solver",
            ],
            timeout=240,
        ) if cli.exists() else CommandResult([str(cli), "prompt"], 1, "", "CLI missing", False, 0.0)
    artifacts = []
    if (out_dir / "core_workflow").exists():
        for path in sorted((out_dir / "core_workflow").rglob("*")):
            if path.is_file():
                artifacts.append(
                    {
                        "path": normalize_path(str(path)),
                        "sha256": sha256_file(path),
                        "size_bytes": path.stat().st_size,
                    }
                )
    payload = {
        "schema": "textlayout.audit.core-install.v1",
        "wheel": normalize_path(str(wheel)) if wheel else None,
        "wheel_sha256": sha256_file(wheel) if wheel else None,
        "build": build_result.to_run_dict(),
        "venv": venv_result.to_run_dict(),
        "install": install_result.to_run_dict(),
        "cli_help": help_result.to_run_dict(),
        "core_workflow": workflow_result.to_run_dict(),
        "generated_artifacts": artifacts,
        "passed": all(
            result.return_code == 0
            for result in (build_result, venv_result, install_result, help_result, workflow_result)
        ),
    }
    json_write(out_dir / "core_install.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output audit directory")
    parser.add_argument("--expected-start-commit", default=None)
    parser.add_argument("--run-core-install", action="store_true")
    parser.add_argument(
        "--fail-on-claim-downgrade",
        action="store_true",
        help="return non-zero when a public claim exceeds computed evidence",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    repository = repository_observation(args.expected_start_commit)
    if repository.get("expected_start_valid") is False:
        print(f"error: {repository['expected_start_error']}", file=sys.stderr)
        return 2

    manifest = deterministic_manifest(repository)
    run_payload = run_record(repository)
    tools = tool_inventory()
    if args.run_core_install:
        run_payload["core_install"] = run_core_install_gate(out_dir)

    json_write(out_dir / "manifest.json", manifest)
    json_write(out_dir / "run.json", run_payload)
    json_write(out_dir / "tool_inventory.json", tools)
    json_write(out_dir / "capability_matrix.json", capability_matrix(tools, run_payload))
    claims = claim_audit()
    json_write(out_dir / "claim_audit.json", claims)
    print(f"wrote audit artifacts to {out_dir}")
    downgrade_count = sum(1 for claim in claims["claims"] if claim["downgrade_required"])
    if args.fail_on_claim_downgrade and downgrade_count:
        print(f"error: {downgrade_count} public claims exceed computed evidence", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
