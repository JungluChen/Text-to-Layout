"""Run and validate Palace's pinned official cavity2d eigenmode example."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

from _palace_common import (
    PALACE_COMMIT,
    PALACE_VERSION,
    ROOT,
    SMOKE_MANIFEST,
    SMOKE_ROOT,
    capture_environment,
    download,
    palace_install_identity,
    read_json,
    sha256_file,
    shlex_quote,
    timestamp,
    windows_to_wsl,
    write_json,
    shell_command,
)

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from textlayout.evidence.canonical import (  # noqa: E402
    CanonicalEvidence,
    SanityCheck,
    compute_evidence_id,
    sha256_json,
    write_canonical,
)
from textlayout.evidence.contract import EvidenceStatus  # noqa: E402
from textlayout.solvers.palace.parser import parse_domain_energy, parse_eigenmodes  # noqa: E402


def _prepare_inputs() -> tuple[Path, Path, dict[str, object]]:
    manifest = read_json(SMOKE_MANIFEST)
    if manifest is None:
        raise RuntimeError(f"invalid smoke manifest: {SMOKE_MANIFEST}")
    if manifest.get("palace_commit") != PALACE_COMMIT:
        raise RuntimeError("smoke manifest Palace commit does not match registry")
    config_info = manifest["config"]
    mesh_info = manifest["mesh"]
    config_source = SMOKE_MANIFEST.parent / str(config_info["path"])
    if sha256_file(config_source) != config_info["sha256"]:
        raise RuntimeError("committed official Palace config hash mismatch")
    config = SMOKE_ROOT / "cavity2d.json"
    mesh = SMOKE_ROOT / "mesh" / "cavity2d.msh"
    SMOKE_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config_source, config)
    download(str(mesh_info["upstream_url"]), mesh, str(mesh_info["sha256"]))
    return config, mesh, manifest


def main() -> int:
    record = palace_install_identity()
    if record is None:
        print("Palace 0.17.0 is not installed; run install_palace.py", file=sys.stderr)
        return 1
    try:
        config, mesh, manifest = _prepare_inputs()
        write_json(capture_environment(), SMOKE_ROOT / "environment.json")
        output = SMOKE_ROOT / "postpro" / "eigenmode"
        if output.is_dir() and SMOKE_ROOT.resolve() in output.resolve().parents:
            shutil.rmtree(output)
        executable = str(record["palace_executable"]).removeprefix("wsl:")
        command = shell_command(
            f"cd {shlex_quote(windows_to_wsl(SMOKE_ROOT))} && "
            f"{shlex_quote(executable)} -np 2 cavity2d.json"
        )
        write_json(
            SMOKE_ROOT / "command.json",
            {
                "command": command,
                "cwd": str(SMOKE_ROOT),
                "palace_version": PALACE_VERSION,
                "palace_commit": PALACE_COMMIT,
                "input_file_hashes": {
                    "cavity2d.json": sha256_file(config),
                    "mesh/cavity2d.msh": sha256_file(mesh),
                },
            },
        )
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        runtime = time.perf_counter() - started
        stdout_path = SMOKE_ROOT / "palace.stdout.txt"
        stderr_path = SMOKE_ROOT / "palace.stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"Palace returned {completed.returncode}")
        eig = output / "eig.csv"
        domain = output / "domain-E.csv"
        modes = parse_eigenmodes(eig)
        energies = parse_domain_energy(domain, mode=modes[0].index)
        if not modes or any(
            not math.isfinite(mode.frequency_ghz) or mode.frequency_ghz <= 0 for mode in modes
        ):
            raise RuntimeError("Palace smoke eigenfrequencies are not finite and positive")
        if not energies or any(not math.isfinite(value) or value <= 0 for value in energies.values()):
            raise RuntimeError("Palace smoke domain energies are not finite and positive")
        outputs = {
            str(path.relative_to(SMOKE_ROOT)).replace("\\", "/"): sha256_file(path)
            for path in (eig, domain)
        }
        inputs = {
            "cavity2d.json": sha256_file(config),
            "mesh/cavity2d.msh": sha256_file(mesh),
        }
        result = {
            "schema": "textlayout.palace-smoke-result.v1",
            "status": "SMOKE_TEST_PASSED",
            "solver_output_parsed": True,
            "palace_version": record["palace_version"],
            "palace_commit": record["palace_commit"],
            "palace_executable_sha256": record["palace_executable_sha256"],
            "official_example": manifest["upstream_example"],
            "command": command,
            "return_code": completed.returncode,
            "runtime_seconds": runtime,
            "frequencies_ghz": [mode.frequency_ghz for mode in modes],
            "domain_energies_j": energies,
            "input_file_hashes": inputs,
            "output_file_hashes": outputs,
            "completed_at": timestamp(),
        }
        write_json(SMOKE_ROOT / "result.json", result)
        extraction = {"parser": "textlayout.solvers.palace.parser.parse_eigenmodes", "mode": 1}
        extraction_hash = sha256_json(extraction)
        evidence_id = compute_evidence_id(
            design_id="palace_official_cavity2d",
            target_quantity="eigenfrequency",
            output_file_hashes=outputs,
            extraction_config_hash=extraction_hash,
        )
        evidence = CanonicalEvidence(
            evidence_id=evidence_id,
            design_id="palace_official_cavity2d",
            design_hash=inputs["cavity2d.json"],
            component="OfficialPalaceCavity2D",
            analysis_scope="official_palace_smoke_eigenmode",
            target_quantity="eigenfrequency",
            extracted_quantity="lowest_positive_eigenfrequency",
            extracted_value=modes[0].frequency_ghz,
            extracted_unit="GHz",
            status=EvidenceStatus.SIMULATION_EXECUTED,
            solver_name="Palace",
            solver_version=str(record["palace_version"]),
            solver_executable_sha256=str(record["palace_executable_sha256"]),
            command=command,
            return_code=completed.returncode,
            runtime_seconds=runtime,
            input_file_hashes=inputs,
            output_file_hashes=outputs,
            parser="textlayout.solvers.palace.parser.parse_eigenmodes",
            parser_version="1",
            extraction_config=extraction,
            extraction_config_hash=extraction_hash,
            sanity_checks=[
                SanityCheck(name="finite_positive_eigenfrequency", passed=True),
                SanityCheck(name="finite_positive_domain_energy", passed=True),
            ],
            timestamp=str(result["completed_at"]),
            warnings=["Installation smoke test is solver-backed but is not physics verification."],
        )
        write_canonical(evidence, SMOKE_ROOT / "canonical_evidence.json")
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        failure = {
            "schema": "textlayout.palace-smoke-result.v1",
            "status": "SIMULATION_INVALID",
            "solver_output_parsed": False,
            "error": str(exc),
            "completed_at": timestamp(),
        }
        write_json(SMOKE_ROOT / "result.json", failure)
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
