"""Shared Palace install discovery across product and toolchain entry points."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from textlayout.evidence.canonical import sha256_file
from textlayout.solvers.palace import capability


def _native_palace(tmp_path: Path, version: str = "0.17.0") -> Path:
    executable = tmp_path / "palace"
    executable.write_text(f"#!/bin/sh\necho 'Palace version: v{version}'\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    return executable


def _record(path: Path, executable: str, digest: str, version: str = "0.17.0") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema": "textlayout.palace-install.v1",
                "status": "INSTALLED",
                "palace_version": version,
                "palace_executable": executable,
                "palace_executable_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.skipif(os.name == "nt", reason="native-Linux executable contract")
def test_native_linux_record_is_live_versioned_hashed_and_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _native_palace(tmp_path)
    record = _record(tmp_path / "install.json", str(executable), sha256_file(executable))

    resolution = capability.resolve_palace_install(record)
    assert resolution.accepted
    assert resolution.capability is not None
    assert resolution.capability.executable == str(executable)
    assert resolution.capability.version == "0.17.0"
    assert resolution.capability.executable_sha256 == sha256_file(executable)

    monkeypatch.setattr(capability, "_INSTALL_RECORD", record)
    detected = capability.detect_palace(
        finder=lambda names, explicit=None, **kwargs: "/usr/bin/mpirun"
        if "mpirun" in names
        else None
    )
    assert detected.executable == str(executable)
    assert detected.mpi_launcher == "/usr/bin/mpirun"


def test_windows_wsl_record_is_accepted_only_after_live_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = "a" * 64
    record = _record(tmp_path / "install.json", "wsl:/opt/palace/bin/palace", digest)
    monkeypatch.setattr(capability, "_probe_executable_version", lambda executable: "0.17.0")
    monkeypatch.setattr(capability, "_hash_executable", lambda executable: digest)

    resolution = capability.resolve_palace_install(record)
    assert resolution.accepted
    assert resolution.capability is not None
    assert resolution.capability.executable == "wsl:/opt/palace/bin/palace"
    assert resolution.capability.executable_sha256 == digest


@pytest.mark.skipif(os.name == "nt", reason="native-Linux executable contract")
def test_stale_native_path_is_rejected(tmp_path: Path) -> None:
    record = _record(tmp_path / "install.json", str(tmp_path / "missing-palace"), "a" * 64)
    resolution = capability.resolve_palace_install(record)
    assert not resolution.accepted
    assert any("does not exist" in reason for reason in resolution.rejection_reasons)


@pytest.mark.skipif(os.name == "nt", reason="native-Linux executable contract")
def test_non_executable_native_path_is_rejected(tmp_path: Path) -> None:
    executable = tmp_path / "palace"
    executable.write_text("Palace version: v0.17.0\n", encoding="utf-8")
    executable.chmod(stat.S_IRUSR | stat.S_IWUSR)
    record = _record(tmp_path / "install.json", str(executable), sha256_file(executable))
    resolution = capability.resolve_palace_install(record)
    assert not resolution.accepted
    assert any("not executable" in reason for reason in resolution.rejection_reasons)


def test_invalid_or_changed_hash_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = "wsl:/opt/palace/bin/palace"
    malformed = _record(tmp_path / "malformed.json", executable, "not-a-hash")
    assert not capability.resolve_palace_install(malformed).accepted

    changed = _record(tmp_path / "changed.json", executable, "a" * 64)
    monkeypatch.setattr(capability, "_probe_executable_version", lambda candidate: "0.17.0")
    monkeypatch.setattr(capability, "_hash_executable", lambda candidate: "b" * 64)
    resolution = capability.resolve_palace_install(changed)
    assert not resolution.accepted
    assert any("does not match" in reason for reason in resolution.rejection_reasons)


def test_recorded_and_live_version_mismatches_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = "wsl:/opt/palace/bin/palace"
    recorded = _record(tmp_path / "recorded.json", executable, "a" * 64, version="0.16.0")
    assert not capability.resolve_palace_install(recorded).accepted

    live = _record(tmp_path / "live.json", executable, "a" * 64)
    monkeypatch.setattr(capability, "_probe_executable_version", lambda candidate: "0.16.0")
    resolution = capability.resolve_palace_install(live)
    assert not resolution.accepted
    assert any("live Palace version" in reason for reason in resolution.rejection_reasons)


def test_rejected_manifest_is_visible_in_absence_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(tmp_path / "install.json", "wsl:/stale/palace", "a" * 64)
    monkeypatch.setattr(capability, "_INSTALL_RECORD", record)
    monkeypatch.setattr(capability, "_probe_executable_version", lambda candidate: None)
    monkeypatch.setattr(
        capability,
        "find_executable",
        lambda names, explicit=None, **kwargs: None,
    )
    detected = capability.detect_palace()
    assert not detected.available
    assert "installation record was rejected" in (detected.unavailable_reason or "")
    assert "live Palace version" in (detected.unavailable_reason or "")


def test_missing_invalid_and_non_installed_records_fail_closed(tmp_path: Path) -> None:
    assert capability.resolve_palace_install(tmp_path / "missing.json").record is None
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    assert "invalid install record" in capability.resolve_palace_install(
        invalid
    ).rejection_reasons[0]
    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    assert not capability.resolve_palace_install(array).accepted
    pending = tmp_path / "pending.json"
    pending.write_text(
        json.dumps(
            {
                "status": "DOWNLOADED",
                "palace_version": "0.17.0",
                "palace_executable": "wsl:/opt/palace",
                "palace_executable_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    assert not capability.resolve_palace_install(pending).accepted


def test_validated_record_projects_only_an_accepted_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _record(tmp_path / "install.json", "wsl:/opt/palace", "a" * 64)
    monkeypatch.setattr(capability, "_probe_executable_version", lambda candidate: "0.17.0")
    monkeypatch.setattr(capability, "_hash_executable", lambda candidate: "a" * 64)
    assert capability.validated_palace_install_record(record) is not None

    monkeypatch.setattr(capability, "_hash_executable", lambda candidate: "b" * 64)
    assert capability.validated_palace_install_record(record) is None


def test_wsl_hash_probe_success_malformed_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    digest = "a" * 64
    monkeypatch.setattr(capability.shutil, "which", lambda name: "/usr/bin/wsl")
    monkeypatch.setattr(
        capability.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, f"{digest}  /opt/palace\n", ""),
    )
    assert capability._hash_executable("wsl:/opt/palace") == digest
    monkeypatch.setattr(
        capability.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "short hash", ""),
    )
    assert capability._hash_executable("wsl:/opt/palace") is None

    def fail(*args, **kwargs):
        raise TimeoutExpired(args[0], 120)

    monkeypatch.setattr(capability.subprocess, "run", fail)
    assert capability._hash_executable("wsl:/opt/palace") is None


def test_version_probe_reads_stderr_and_handles_process_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        capability.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, "", "Palace version: v0.17.0"),
    )
    assert capability._probe(["palace", "--version"]) == "0.17.0"

    monkeypatch.setattr(
        capability.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cannot execute")),
    )
    assert capability._probe(["palace", "--version"]) is None


def test_executable_version_probe_tries_fallback_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([None, "0.17.0"])
    commands: list[list[str]] = []

    def probe(command: list[str]) -> str | None:
        commands.append(command)
        return next(answers)

    monkeypatch.setattr(capability, "_probe", probe)
    assert capability._probe_executable_version("palace") == "0.17.0"
    assert commands[0][-1] == "--version"
    assert commands[1][-1] == "--help"
    monkeypatch.setattr(capability, "_probe", lambda command: None)
    assert capability._probe_executable_version("palace") is None


@pytest.mark.parametrize(
    ("return_code", "stdout", "expected"),
    [
        (1, "{}", None),
        (0, "not-json", None),
        (0, "[]", None),
        (0, '{"RepoDigests":["palace@sha256:abc"]}', "sha256:abc"),
        (0, '{"RepoDigests":[],"Id":"sha256:def"}', "sha256:def"),
        (0, '{"RepoDigests":[],"Id":"local"}', None),
    ],
)
def test_oci_inspection_is_fail_closed(
    return_code: int,
    stdout: str,
    expected: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        capability.subprocess,
        "run",
        lambda *args, **kwargs: CompletedProcess(args[0], return_code, stdout, ""),
    )
    assert capability._inspect_oci_image("docker", "palace:0.17.0") == expected


def test_oci_inspection_handles_execution_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        capability.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("docker missing")),
    )
    assert capability._inspect_oci_image("docker", "palace:0.17.0") is None


def test_sif_and_oci_detection_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sif = tmp_path / "palace.sif"
    sif.write_bytes(b"sif-image")
    monkeypatch.setattr(capability, "_probe", lambda command: "0.17.0")

    sif_capability = capability._detect_sif(
        str(sif),
        finder=lambda *args, **kwargs: "apptainer",
        probe_version=True,
    )
    assert sif_capability is not None
    assert sif_capability.container_image == str(sif)
    assert sif_capability.version == "0.17.0"
    assert capability._detect_sif(
        str(sif), finder=lambda *args, **kwargs: None, probe_version=False
    ) is None
    assert capability._detect_sif(
        str(tmp_path / "missing.sif"),
        finder=lambda *args, **kwargs: "apptainer",
        probe_version=False,
    ) is None

    monkeypatch.setattr(capability, "_inspect_oci_image", lambda engine, image: "sha256:abc")
    monkeypatch.setattr(capability, "_probe_oci_version", lambda engine, image: "0.17.0")
    oci = capability._detect_oci(
        "palace:0.17.0",
        finder=lambda *args, **kwargs: "docker",
        probe_version=True,
    )
    assert oci is not None
    assert oci.container_digest == "sha256:abc"
    assert oci.version == "0.17.0"
    assert capability._detect_oci(
        "palace:0.17.0", finder=lambda *args, **kwargs: None, probe_version=False
    ) is None


def test_detect_container_fallbacks_and_capability_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_record = tmp_path / "missing-install.json"
    monkeypatch.setattr(capability, "_INSTALL_RECORD", missing_record)
    monkeypatch.setattr(capability, "_detect_sif", lambda *args, **kwargs: None)
    container = capability.PalaceCapability(
        execution_kind="container",
        version="0.17.0",
        container_engine="docker",
        container_image="palace:0.17.0",
        container_digest="sha256:abc",
        mpi_launcher="docker:internal",
    )
    monkeypatch.setattr(capability, "_detect_oci", lambda *args, **kwargs: container)
    detected = capability.detect_palace(
        container_image="palace:0.17.0",
        finder=lambda *args, **kwargs: None,
    )
    assert detected == container
    report = capability.capability_report(detected)
    assert report["available"] is True
    assert report["identified"] is True
    assert report["status"] == "AVAILABLE"


def test_detect_direct_executable_without_version_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = _native_palace(tmp_path)
    missing_record = tmp_path / "missing-install.json"
    monkeypatch.setattr(capability, "_INSTALL_RECORD", missing_record)

    def finder(names, explicit=None, **kwargs):
        if "palace" in names:
            return str(executable)
        if "mpirun" in names:
            return "/usr/bin/mpirun"
        return None

    detected = capability.detect_palace(
        str(executable),
        container_digest="sha256:container",
        probe_version=False,
        finder=finder,
    )
    assert detected.executable == str(executable)
    assert detected.version is None
    assert detected.executable_sha256 == sha256_file(executable)
    assert detected.container_digest == "sha256:container"
