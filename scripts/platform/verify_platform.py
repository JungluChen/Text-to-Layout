#!/usr/bin/env python3
"""Collect and render evidence-backed macOS or WSL2 core certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "textlayout.platform-certification.v1"
PROMPT = "Create a 0.6 pF IDC on silicon at 6 GHz with 2 um min gap"
SOLVER_PROMPTS = {
    "FastHenry": "Create a 3 nH 4-turn spiral inductor on silicon",
    "openEMS": "Create a 50 ohm CPW on silicon at 6 GHz",
    "JoSIM": "Create a SQUID on silicon with a JoSIM circuit check",
}
SUPPORT_STATES = frozenset(
    {
        "UNTESTED",
        "CORE_TESTED",
        "CORE_CERTIFIED",
        "SOLVER_PARTIAL",
        "SOLVER_CERTIFIED",
        "UNSUPPORTED",
    }
)
SOLVER_STAGES = frozenset(
    {
        "NOT_INSTALLED",
        "FOUND",
        "PROBE_PASS",
        "EXECUTION_PASS",
        "OUTPUT_PARSED",
        "CONVERGENCE_PROVEN",
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def run_command(
    name: str,
    command: list[str],
    environment: dict[str, str],
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimed out after {timeout_seconds} seconds."
    return {
        "name": name,
        "command": command,
        "exit_code": exit_code,
        "runtime_seconds": round(time.monotonic() - started, 6),
        "stdout": stdout,
        "stderr": stderr,
    }


def parse_json_output(record: dict[str, Any]) -> dict[str, Any] | None:
    try:
        payload = json.loads(record["stdout"])
    except (json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def junit_summary(path: Path) -> dict[str, int] | None:
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return None

    def count(name: str) -> int:
        return int(suite.get(name, 0) or 0)

    total = count("tests")
    failed = count("failures") + count("errors")
    skipped = count("skipped")
    return {
        "total": total,
        "passed": total - failed - skipped,
        "failed": failed,
        "skipped": skipped,
    }


def artifact_evidence(prompt_record: dict[str, Any]) -> dict[str, Any]:
    payload = parse_json_output(prompt_record)
    if payload is None:
        return {"valid": False, "reason": "prompt stdout was not JSON"}
    output_dir = Path(str(payload.get("output_dir", "")))
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or not str(output_dir):
        return {"valid": False, "reason": "prompt omitted artifact paths"}
    files: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for name, relative in sorted(artifacts.items()):
        candidate = output_dir / str(relative)
        exists = candidate.is_file() and candidate.stat().st_size > 0
        files[name] = {
            "path": candidate.as_posix(),
            "exists": exists,
            "size": candidate.stat().st_size if exists else 0,
            "sha256": sha256(candidate) if exists else None,
        }
        if not exists:
            missing.append(f"{name}: {relative}")
    return {
        "valid": not missing,
        "missing_or_empty": missing,
        "simulation_status": payload.get("simulation_status"),
        "files": files,
    }


def simulation_stage(evidence: dict[str, Any]) -> str:
    """Map a prompt's canonical simulation status to the highest proven stage."""
    status = str(evidence.get("simulation_status") or "")
    if status == "NUMERICALLY_CONVERGED":
        return "CONVERGENCE_PROVEN"
    if status in {"OUTPUT_PARSED", "PHYSICS_VERIFIED"}:
        return "OUTPUT_PARSED"
    if status in {"SIMULATION_EXECUTED", "executed"}:
        return "EXECUTION_PASS"
    return "PROBE_PASS"


def host_evidence(platform_name: str) -> dict[str, Any]:
    release = platform.release()
    proc_path = Path("/proc/version")
    proc_version = (
        proc_path.read_text(encoding="utf-8", errors="replace").strip()
        if proc_path.is_file()
        else None
    )
    is_wsl = bool(os.environ.get("WSL_INTEROP")) or "microsoft" in release.lower()
    wsl_version = None
    if is_wsl:
        wsl_version = (
            2 if "wsl2" in release.lower() or "microsoft-standard" in release.lower() else 1
        )
    lsb = None
    repository_filesystem = None
    solver_filesystem = None
    native_root = Path(
        os.environ.get(
            "TEXTLAYOUT_WSL_NATIVE_ROOT",
            Path.home() / ".local" / "share" / "textlayout",
        )
    )
    if is_wsl:
        lsb_result = subprocess.run(
            ["lsb_release", "-a"], capture_output=True, text=True, check=False
        )
        lsb = lsb_result.stdout.strip() if lsb_result.returncode == 0 else None
        repo_fs = subprocess.run(
            ["findmnt", "-n", "-o", "FSTYPE", "-T", str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        repository_filesystem = repo_fs.stdout.strip() if repo_fs.returncode == 0 else None
        solver_fs = subprocess.run(
            ["findmnt", "-n", "-o", "FSTYPE", "-T", str(native_root.parent)],
            capture_output=True,
            text=True,
            check=False,
        )
        solver_filesystem = solver_fs.stdout.strip() if solver_fs.returncode == 0 else None
    return {
        "requested_platform": platform_name,
        "os": platform.system(),
        "os_release": release,
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "uname": " ".join(platform.uname()),
        "wsl_detected": is_wsl,
        "wsl_version": wsl_version,
        "wsl_distribution": os.environ.get("WSL_DISTRO_NAME") if is_wsl else None,
        "proc_version": proc_version,
        "lsb_release": lsb,
        "repository_filesystem": repository_filesystem,
        "solver_root": str(native_root),
        "solver_filesystem": solver_filesystem,
        "windows_mount_warning": (
            "Repository is under /mnt; ordinary source use is allowed, but heavy "
            f"solver builds should use WSL-native storage at {native_root}."
            if is_wsl and str(ROOT).startswith("/mnt/")
            else None
        ),
    }


def solver_matrix(doctor: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if doctor is None:
        return {}
    wanted = {
        "FasterCap": "FasterCap/FastCap",
        "FastHenry": "FastHenry/FastHenry2",
        "openEMS": "openEMS",
        "Palace": "Palace",
        "JoSIM": "JoSIM",
    }
    external = doctor.get("external_solvers", {})
    matrix: dict[str, dict[str, Any]] = {}
    for display, key in wanted.items():
        source = external.get(key, {})
        stage = source.get("evidence_stage", "NOT_INSTALLED")
        support = source.get("support_state", "UNTESTED")
        matrix[display] = {
            "support_state": support if support in SUPPORT_STATES else "UNTESTED",
            "evidence_stage": stage if stage in SOLVER_STAGES else "NOT_INSTALLED",
            "path": source.get("path"),
            "version": source.get("version"),
            "executable_sha256": source.get("executable_sha256"),
            "probe": source.get("smoke_test"),
            "execution_evidence": None,
        }
    return matrix


def run_installed_solver_smokes(
    doctor: dict[str, Any],
    environment: dict[str, str],
    prefix: list[str],
    run_dir: Path,
    idc_prompt_record: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Execute and classify solvers that Doctor has actually probed.

    Solver smoke evidence is separate from core certification: an optional
    solver failure cannot downgrade the core, and a passing version probe
    cannot be promoted to execution evidence.
    """
    external = doctor.get("external_solvers", {})
    results: dict[str, dict[str, Any]] = {}

    def probe_passed(key: str) -> bool:
        return external.get(key, {}).get("evidence_stage") == "PROBE_PASS"

    if probe_passed("FasterCap/FastCap"):
        evidence = artifact_evidence(idc_prompt_record)
        results["FasterCap"] = {
            "command": idc_prompt_record,
            "artifact_evidence": evidence,
            "evidence_stage": simulation_stage(evidence),
        }

    prompt_requirements = {
        "FastHenry": ("FastHenry/FastHenry2",),
        "openEMS": (
            "openEMS",
            "Octave",
            "Octave openEMS path",
            "Octave CSXCAD path",
            "scikit-rf",
        ),
        "JoSIM": ("JoSIM",),
    }
    for solver, requirements in prompt_requirements.items():
        if not all(probe_passed(key) for key in requirements):
            continue
        output = run_dir / f"solver_smoke_{solver.lower()}"
        command = run_command(
            f"solver_smoke_{solver.lower()}",
            [
                *prefix,
                "textlayout",
                "prompt",
                SOLVER_PROMPTS[solver],
                "--out",
                str(output),
            ],
            environment,
            1800,
        )
        evidence = artifact_evidence(command)
        results[solver] = {
            "command": command,
            "artifact_evidence": evidence,
            "evidence_stage": simulation_stage(evidence),
        }

    if probe_passed("Palace"):
        command = run_command(
            "solver_smoke_palace",
            [*prefix, "python", "scripts/external/run_palace_smoke.py"],
            environment,
            1800,
        )
        result_path = ROOT / "out" / "external" / "palace_smoke" / "result.json"
        result = (
            json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
        )
        parsed = isinstance(result, dict) and result.get("solver_output_parsed") is True
        results["Palace"] = {
            "command": command,
            "result": result,
            "result_sha256": sha256(result_path) if result_path.is_file() else None,
            "evidence_stage": "OUTPUT_PARSED" if parsed else "PROBE_PASS",
        }
    return results


def record_python_run(platform_name: str, python_version: str, *, quick: bool) -> dict[str, Any]:
    token = python_version.replace(".", "")
    run_parent = ROOT / "out" / "platform" / "runs"
    run_parent.mkdir(parents=True, exist_ok=True)
    environment_parent = Path(
        tempfile.mkdtemp(prefix=f"clean-{platform_name}-py{token}-", dir=run_parent)
    )
    environment_dir = environment_parent / ".venv"
    environment = dict(os.environ)
    environment["UV_PROJECT_ENVIRONMENT"] = str(environment_dir)
    relevant_environment = {
        key: environment[key]
        for key in sorted(environment)
        if key.startswith("TEXTLAYOUT_") or key == "UV_PROJECT_ENVIRONMENT"
    }
    prefix = ["uv", "run", "--python", python_version]
    run_dir = Path(tempfile.mkdtemp(prefix=f"{platform_name}-py{token}-", dir=run_parent))
    junit = run_dir / "test_report.xml"
    prompt_one = run_dir / "idc_1"
    prompt_two = run_dir / "idc_2"
    pytest_targets = ["tests/textlayout_suite/test_api.py"] if quick else []
    specs = [
        ("uv_version", ["uv", "--version"], 120),
        (
            "sync",
            ["uv", "sync", "--frozen", "--dev", "--python", python_version],
            600,
        ),
        ("doctor_json", [*prefix, "textlayout", "doctor", "--json"], 120),
        ("cli_help", [*prefix, "textlayout", "--help"], 120),
        (
            "readme_claim_audit",
            [*prefix, "python", "scripts/validate_readme_claims.py"],
            120,
        ),
        (
            "namespace_check",
            [*prefix, "python", "scripts/check_namespace_boundary.py", "--check"],
            120,
        ),
        ("ruff", [*prefix, "ruff", "check", "."], 300),
        ("mypy", [*prefix, "mypy"], 600),
        (
            "pytest",
            [*prefix, "pytest", *pytest_targets, f"--junit-xml={junit}"],
            1800,
        ),
        (
            "project_status_check",
            [
                *prefix,
                "python",
                "scripts/generate_project_status.py",
                "--check",
            ],
            120,
        ),
        ("build", ["uv", "build"], 600),
        (
            "api_smoke",
            [*prefix, "pytest", "tests/textlayout_suite/test_api.py", "-q"],
            300,
        ),
        (
            "prompt_1",
            [*prefix, "textlayout", "prompt", PROMPT, "--out", str(prompt_one)],
            900,
        ),
        (
            "prompt_2",
            [*prefix, "textlayout", "prompt", PROMPT, "--out", str(prompt_two)],
            900,
        ),
    ]
    commands = [
        run_command(name, command, environment, timeout) for name, command, timeout in specs
    ]
    by_name = {record["name"]: record for record in commands}
    doctor = parse_json_output(by_name["doctor_json"])
    first = artifact_evidence(by_name["prompt_1"])
    second = artifact_evidence(by_name["prompt_2"])
    deterministic = all(
        first.get("files", {}).get(name, {}).get("sha256")
        == second.get("files", {}).get(name, {}).get("sha256")
        for name in ("layout", "gds")
    )
    tests = junit_summary(junit)
    command_pass = all(record["exit_code"] == 0 for record in commands)
    core_dependencies = doctor.get("core_dependencies", {}) if doctor else {}
    return {
        "python_requested": python_version,
        "python_actual": doctor.get("runtime", {}).get("python") if doctor else None,
        "environment": relevant_environment,
        "isolated_environment": str(environment_dir),
        "quick": quick,
        "tool_versions": {
            "uv": by_name["uv_version"]["stdout"].strip(),
            "textlayout": doctor.get("runtime", {}).get("textlayout") if doctor else None,
            "gdsfactory": core_dependencies.get("gdsfactory", {}).get("version"),
            "klayout": core_dependencies.get("klayout.db", {}).get("version"),
        },
        "commands": commands,
        "doctor": doctor,
        "tests": tests,
        "prompt": {
            "input": PROMPT,
            "input_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
            "run_1": first,
            "run_2": second,
            "layout_and_gds_deterministic": deterministic,
        },
        "core_pass": (
            command_pass
            and first.get("valid") is True
            and second.get("valid") is True
            and deterministic
        ),
        "solver_smokes": (
            run_installed_solver_smokes(
                doctor,
                environment,
                prefix,
                run_dir,
                by_name["prompt_1"],
            )
            if platform_name == "wsl2" and not quick and doctor
            else {}
        ),
    }


def collect(
    platform_name: str,
    python_versions: list[str],
    *,
    quick: bool,
    blocked_reason: str | None,
) -> dict[str, Any]:
    host = host_evidence(platform_name)
    input_hashes = {
        path.name: sha256(path)
        for path in (ROOT / "pyproject.toml", ROOT / "uv.lock")
        if path.is_file()
    }
    base = {
        "schema": SCHEMA,
        "platform": platform_name,
        "git_sha": git_sha(),
        "host": host,
        "input_hashes": input_hashes,
    }
    if blocked_reason:
        return {
            **base,
            "real_execution": False,
            "support_state": "UNTESTED",
            "certification": "BLOCKED_AWAITING_REAL_EXECUTION",
            "blocking_reason": blocked_reason,
            "core_pass": False,
            "python_runs": [],
            "solvers": {},
            "capabilities": {},
        }
    platform_matches = (
        platform_name == "macos" and host["os"] == "Darwin" and host["architecture"] == "arm64"
    ) or (platform_name == "wsl2" and host["wsl_detected"] is True and host["wsl_version"] == 2)
    if not platform_matches:
        raise SystemExit(f"host does not match requested platform: {host}")
    runs = [record_python_run(platform_name, version, quick=quick) for version in python_versions]
    core_pass = bool(runs) and all(run["core_pass"] for run in runs)
    certified = core_pass and not quick
    first_doctor = next((run["doctor"] for run in runs if run["doctor"]), None)
    solver_smokes = next((run["solver_smokes"] for run in runs if run["solver_smokes"]), {})
    solvers = solver_matrix(first_doctor)
    for name, smoke in solver_smokes.items():
        if name not in solvers:
            continue
        solvers[name]["evidence_stage"] = smoke["evidence_stage"]
        solvers[name]["execution_evidence"] = smoke
        if smoke["evidence_stage"] in {
            "OUTPUT_PARSED",
            "CONVERGENCE_PROVEN",
        }:
            solvers[name]["support_state"] = "SOLVER_CERTIFIED"
    support_state = "CORE_CERTIFIED" if certified else "CORE_TESTED"
    return {
        **base,
        "real_execution": True,
        "support_state": support_state,
        "certification": support_state,
        "blocking_reason": None,
        "core_pass": core_pass,
        "python_runs": runs,
        "solvers": solvers,
        "capabilities": first_doctor.get("capabilities", {}) if first_doctor else {},
    }


def render_markdown(evidence: dict[str, Any], source_json: str) -> str:
    tick = chr(96)
    lines = [
        f"# {evidence['platform']} platform certification",
        "",
        "<!-- GENERATED_CURRENT_STATUS: scripts/platform/verify_platform.py; do not hand-edit. -->",
        "",
        f"**Evidence source:** {tick}{source_json}{tick}",
        f"**Git SHA:** {tick}{evidence['git_sha']}{tick}",
        f"**Real execution:** {tick}{evidence['real_execution']}{tick}",
        f"**Support state:** {tick}{evidence['support_state']}{tick}",
        f"**Core pass:** {tick}{evidence['core_pass']}{tick}",
        "",
    ]
    if evidence.get("blocking_reason"):
        lines += [
            "## Certification blocker",
            "",
            evidence["blocking_reason"],
            "",
            "This document is an explicit non-certification record. "
            "Ubuntu CI is not WSL2 evidence.",
            "",
        ]
    host = evidence["host"]
    lines += [
        "## Host",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| OS | {host['os']} {host['os_release']} |",
        f"| Architecture | {host['architecture']} |",
        f"| WSL detected/version | {host['wsl_detected']} / {host['wsl_version']} |",
        f"| WSL distribution | {host.get('wsl_distribution') or 'not applicable'} |",
        f"| Repository filesystem | {host.get('repository_filesystem') or 'not recorded'} |",
        f"| Solver root/filesystem | {host.get('solver_root') or 'not recorded'} / "
        f"{host.get('solver_filesystem') or 'not recorded'} |",
        "",
    ]
    if host.get("windows_mount_warning"):
        lines += [f"> {host['windows_mount_warning']}", ""]
    lines += [
        "## Core runs",
        "",
        "| Python | Tests | Commands | Deterministic IDC | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for run in evidence.get("python_runs", []):
        tests = run.get("tests") or {}
        test_text = (
            f"{tests.get('passed', 0)} passed / {tests.get('failed', 0)} failed / "
            f"{tests.get('skipped', 0)} skipped"
        )
        passed = sum(command["exit_code"] == 0 for command in run["commands"])
        lines.append(
            f"| {run.get('python_actual') or run['python_requested']} | {test_text} | "
            f"{passed}/{len(run['commands'])} passed | "
            f"{run['prompt']['layout_and_gds_deterministic']} | "
            f"{'PASS' if run['core_pass'] else 'FAIL'} |"
        )
    if not evidence.get("python_runs"):
        lines.append("| not executed | n/a | n/a | n/a | BLOCKED |")
    lines += [
        "",
        "## External solvers",
        "",
        "| Solver | Support | Evidence stage | Version | Identity |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, solver in evidence.get("solvers", {}).items():
        identity = solver.get("executable_sha256") or solver.get("path") or "not installed"
        lines.append(
            f"| {name} | {tick}{solver['support_state']}{tick} | "
            f"{tick}{solver['evidence_stage']}{tick} | "
            f"{solver.get('version') or 'unknown'} | {tick}{identity}{tick} |"
        )
    if not evidence.get("solvers"):
        lines.append(
            f"| none executed on this host | {tick}UNTESTED{tick} | "
            f"{tick}NOT_INSTALLED{tick} | unknown | n/a |"
        )
    lines += [
        "",
        "## Certification boundary",
        "",
        "Core certification covers locked installation, imports, CLI/API, "
        "deterministic DSL/layout/GDS, KLayout readback, verification, tests, "
        "static checks, documentation gates, and package build.",
        "External solver certification requires separate execution, solver-owned "
        "output parsing, and convergence evidence. A found binary or passing "
        f"probe is only {tick}PROBE_PASS{tick}.",
        "",
    ]
    failures = [
        command
        for run in evidence.get("python_runs", [])
        for command in run["commands"]
        if command["exit_code"] != 0
    ]
    if failures:
        lines += ["## Failed commands", ""]
        for command in failures:
            lines.append(
                f"- {tick}{command['name']}{tick} exited {tick}{command['exit_code']}{tick}."
            )
        lines.append("")
    return "\n".join(lines)


def write_evidence(evidence: dict[str, Any], output: Path, markdown: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown.write_text(
        render_markdown(evidence, output.relative_to(ROOT).as_posix()),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("macos", "wsl2"), required=True)
    parser.add_argument("--python-version", action="append", dest="python_versions")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--blocked-reason")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args(argv)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    markdown = args.markdown_out if args.markdown_out.is_absolute() else ROOT / args.markdown_out
    if args.render_only:
        evidence = json.loads(output.read_text(encoding="utf-8"))
        markdown.write_text(
            render_markdown(evidence, output.relative_to(ROOT).as_posix()),
            encoding="utf-8",
        )
        return 0
    versions = args.python_versions or (["3.11", "3.12"] if args.platform == "macos" else ["3.11"])
    evidence = collect(
        args.platform,
        versions,
        quick=args.quick,
        blocked_reason=args.blocked_reason,
    )
    write_evidence(evidence, output, markdown)
    print(
        json.dumps(
            {
                "output": str(output),
                "markdown": str(markdown),
                "support_state": evidence["support_state"],
                "real_execution": evidence["real_execution"],
            },
            indent=2,
        )
    )
    if evidence["real_execution"] and evidence["core_pass"]:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
