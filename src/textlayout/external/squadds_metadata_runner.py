"""Run the audited optional metadata worker with retained process evidence."""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from textlayout.external._squadds_metadata_worker import DATA_SHA256
from textlayout.external.squadds_metadata_assessment import MetadataAssessment, assess_metadata


@dataclass(frozen=True)
class MetadataRun:
    """Process completion and data agreement, never electrical validation."""

    output_dir: str
    return_code: int | None
    assessment: MetadataAssessment | None
    failure_reason: str | None


def run_metadata(
    database: Path, *, python: Path, output_dir: Path, timeout_seconds: float = 120,
) -> MetadataRun:
    """Run once in a fresh directory; retain failures and never resume implicitly.

    Reject bad input/timeout before creating output. Python is explicitly chosen
    by the caller; the manifest records its path/hash, not a trust attestation.
    Offline library flags are not an operating-system network sandbox.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    with database.open("rb") as stream:
        payload = stream.read(1024 * 1024 + 1)
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise ValueError("Expected pinned dataset bytes")
    directory = output_dir.expanduser().absolute()
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / "database.json"
    source.write_bytes(payload)
    worker = Path(__file__).with_name("_squadds_metadata_worker.py")
    # Preserve a virtual environment's executable path (do not resolve its symlink).
    interpreter = python.expanduser().absolute()
    command = [str(interpreter), "-I", str(worker), str(source), str(directory / "raw.json")]
    worker_hash = hashlib.sha256(worker.read_bytes()).hexdigest()
    interpreter_hash = None
    environment = os.environ.copy()
    overrides = {"HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                 "QT_QPA_PLATFORM": "offscreen", "PYTHONNOUSERSITE": "1"}
    for name in ("MPLCONFIGDIR", "XDG_CACHE_HOME", "HF_HOME"):
        overrides[name] = str(directory / "cache" / name.lower())
    environment.update(overrides)
    code = None
    assessment = None
    failure = None
    started = time.monotonic()
    with (directory / "stdout.txt").open("wb") as stdout, (directory / "stderr.txt").open("wb") as stderr:
        try:
            interpreter_hash = hashlib.sha256(interpreter.read_bytes()).hexdigest()
            process = subprocess.run(command, cwd=directory, env=environment, stdout=stdout,
                                     stderr=stderr, timeout=timeout_seconds, check=False)
            code = process.returncode
            if code != 0:
                raise ValueError("Worker failed; inspect stderr.txt")
            if hashlib.sha256(worker.read_bytes()).hexdigest() != worker_hash:
                raise ValueError("Worker changed during execution")
            if hashlib.sha256(interpreter.read_bytes()).hexdigest() != interpreter_hash:
                raise ValueError("Interpreter changed during execution")
            if source.read_bytes() != payload:
                raise ValueError("Input changed during execution")
            with (directory / "raw.json").open("rb") as raw:
                encoded = raw.read(1024 * 1024 + 1)
            if len(encoded) > 1024 * 1024:
                raise ValueError("Raw packet exceeds 1 MiB")
            assessment = assess_metadata(payload, json.loads(encoded))
        except subprocess.TimeoutExpired:
            failure = "Worker timed out; direct child reaped, partial logs retained; no resume"
        except (OSError, ValueError, TypeError) as exc:
            failure = f"{type(exc).__name__}: {exc}"
    result = MetadataRun(str(directory), code, assessment, failure)
    (directory / "result.json").write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": "textlayout.squadds-metadata-process.v1", "command": command,
        "timeout_seconds": timeout_seconds, "elapsed_seconds": time.monotonic() - started,
        "environment_overrides": overrides, "worker_sha256": worker_hash,
        "interpreter_sha256": interpreter_hash, "return_code": code,
        "physics_verified": False, "electrical_reproduction_status": "NOT_EVALUATED",
        "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in directory.iterdir() if p.is_file()},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return result
