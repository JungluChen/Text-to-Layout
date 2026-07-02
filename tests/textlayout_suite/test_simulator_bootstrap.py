"""Simulator bootstrap: checker policy, detection parity, packaging files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bootstrap_simulators  # noqa: E402
import check_simulators  # noqa: E402
import install_josim  # noqa: E402

_SIM_ENV_VARS = (
    "TEXTLAYOUT_JOSIM",
    "TEXTLAYOUT_PSCAN2",
    "TEXTLAYOUT_WRSPICE",
    "TEXTLAYOUT_TOOLS_DIR",
    "TEXTLAYOUT_STRICT_SIMULATORS",
)


@pytest.fixture()
def no_simulators(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A world with empty PATH hits, no env overrides, and an empty tools dir."""
    for name in _SIM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(check_simulators.shutil, "which", lambda *_: None)
    monkeypatch.setattr(check_simulators, "find_spec", lambda *_: None)
    tools = tmp_path / "tools"
    tools.mkdir()
    return tools


def test_checker_honest_when_nothing_is_installed(no_simulators: Path) -> None:
    reports = check_simulators.collect_reports(no_simulators)
    by_name = {report.name: report for report in reports}
    assert not by_name["JoSIM"].available
    assert by_name["JoSIM"].status == check_simulators.STATUS_ABSENT
    assert by_name["PSCAN2"].status == check_simulators.STATUS_MANUAL
    assert by_name["WRspice"].status == check_simulators.STATUS_MANUAL


def test_non_strict_checker_exits_zero_without_simulators(
    no_simulators: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check_simulators.main(["--tools-dir", str(no_simulators)]) == 0
    out = capsys.readouterr().out
    assert "JoSIM" in out and "PSCAN2" in out and "WRspice" in out


def test_strict_checker_exits_nonzero_when_josim_missing(
    no_simulators: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check_simulators.main(["--tools-dir", str(no_simulators), "--strict"]) == 1
    out = capsys.readouterr().out
    assert "STRICT MODE FAILURE" in out
    # Optional backends are skipped, not failed, in strict mode.
    reports = check_simulators.collect_reports(no_simulators, strict=True)
    by_name = {report.name: report for report in reports}
    assert by_name["JoSIM"].status == check_simulators.STATUS_STRICT_MISSING
    assert by_name["PSCAN2"].status == check_simulators.STATUS_SKIPPED_OPTIONAL
    assert by_name["WRspice"].status == check_simulators.STATUS_SKIPPED_OPTIONAL


def test_josim_env_var_override(no_simulators: Path, tmp_path: Path) -> None:
    fake = tmp_path / "my-josim-cli.exe"
    fake.write_text("stub", encoding="ascii")
    detection = check_simulators.detect_josim(no_simulators, env={"TEXTLAYOUT_JOSIM": str(fake)})
    assert detection.available
    assert detection.method == "env:TEXTLAYOUT_JOSIM"
    assert detection.path == str(fake)


def test_josim_tools_dir_detection(no_simulators: Path) -> None:
    bin_dir = no_simulators / "josim" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "josim-cli").write_text("stub", encoding="ascii")
    detection = check_simulators.detect_josim(no_simulators, env={})
    assert detection.available
    assert detection.method == "tools_dir"
    assert detection.path == str(bin_dir / "josim-cli")


def test_josim_path_detection(
    no_simulators: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "josim-cli"
    fake.write_text("stub", encoding="ascii")
    monkeypatch.setattr(
        check_simulators.shutil,
        "which",
        lambda name: str(fake) if name == "josim-cli" else None,
    )
    detection = check_simulators.detect_josim(no_simulators, env={})
    assert detection.available
    assert detection.method == "path"


def test_runtime_josim_adapter_matches_checker_priority(
    no_simulators: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The textlayout adapter and the checker must find the same executable."""
    from textlayout.simulation import JoSIMCircuitAdapter

    bin_dir = no_simulators / "josim" / "bin"
    bin_dir.mkdir(parents=True)
    tool_install = bin_dir / "josim-cli"
    tool_install.write_text("stub", encoding="ascii")
    monkeypatch.setenv("TEXTLAYOUT_TOOLS_DIR", str(no_simulators))

    adapter_path = JoSIMCircuitAdapter().discover()
    checker_path = check_simulators.detect_josim().path
    assert adapter_path == str(tool_install) == checker_path

    # And the env var must beat the tools dir in both.
    override = no_simulators / "override-josim.exe"
    override.write_text("stub", encoding="ascii")
    monkeypatch.setenv("TEXTLAYOUT_JOSIM", str(override))
    assert JoSIMCircuitAdapter().discover() == str(override)
    assert check_simulators.detect_josim().path == str(override)


def test_bootstrap_does_not_block_on_missing_optional_simulators(
    no_simulators: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = bootstrap_simulators.main(["--detect-only", "--tools-dir", str(no_simulators)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "JoSIM (primary)" in out
    assert "make demo-jpa" in out
    manifest = json.loads((no_simulators / "simulators.json").read_text(encoding="utf-8"))
    assert manifest["pscan2"]["status"] == check_simulators.STATUS_MANUAL
    assert manifest["wrspice"]["status"] == check_simulators.STATUS_MANUAL


def test_install_josim_detect_only_never_installs(no_simulators: Path) -> None:
    detection = install_josim.ensure_josim(no_simulators, detect_only=True)
    assert not detection.available
    assert not (no_simulators / "josim").exists()
    assert not (no_simulators / "build").exists()


def test_install_josim_adopts_existing_unpacked_release(no_simulators: Path) -> None:
    legacy_bin = no_simulators / "josim-v9.9" / "bin"
    legacy_bin.mkdir(parents=True)
    (legacy_bin / "josim-cli").write_text("stub", encoding="ascii")
    installed = install_josim._normalise_existing(no_simulators)
    assert installed == no_simulators / "josim" / "bin" / "josim-cli"
    assert installed.is_file()


def test_makefile_has_simulator_targets() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    for target in (
        "setup-simulators:",
        "check-simulators:",
        "demo-jpa:",
        "demo-jpa-strict:",
        "docker-simulators:",
    ):
        assert target in makefile, target
    assert "scripts/bootstrap_simulators.py" in makefile
    assert "scripts/check_simulators.py" in makefile


def test_docker_and_devcontainer_exist_and_are_wired() -> None:
    dockerfile = (REPO_ROOT / "docker" / "simulators.Dockerfile").read_text(encoding="utf-8")
    assert "bootstrap_simulators.py" in dockerfile
    assert "check_simulators.py" in dockerfile
    devcontainer = json.loads(
        (REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    )
    assert devcontainer["build"]["dockerfile"] == "../docker/simulators.Dockerfile"
    assert "check-simulators" in devcontainer["postCreateCommand"]


def test_readme_documents_setup_flow() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Simulator Setup" in readme
    for command in ("make setup-simulators", "make check-simulators", "make demo-jpa"):
        assert command in readme, command
    assert "PHYSICS_VERIFIED" in readme


def test_tools_dir_is_gitignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".tools/" in gitignore.splitlines()
