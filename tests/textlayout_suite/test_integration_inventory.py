"""Catalog runtime inventory: FOUND/MISSING/BROKEN/NOT_PROBED without execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from textlayout.integrations import load_targets
from textlayout.integrations.inventory import (
    BROKEN,
    FOUND,
    MISSING,
    NOT_PROBED,
    ToolProbeSpec,
    load_probe_specs,
    probe_inventory,
    probe_target,
    summarize_inventory,
    tool_cache_roots,
)


def test_probe_specs_cover_every_catalog_target_exactly_once() -> None:
    specs = load_probe_specs()
    assert sorted(specs) == list(range(1, 101))
    kinds = {spec.kind for spec in specs.values()}
    assert kinds == {"python", "executable", "python+executable", "none"}


def test_inventory_probes_all_targets_with_closed_vocabulary(tmp_path: Path) -> None:
    probes = probe_inventory(roots=[tmp_path])
    assert len(probes) == 100
    assert {probe.status for probe in probes} <= {FOUND, MISSING, BROKEN, NOT_PROBED}
    by_name = {probe.name: probe for probe in probes}
    # Core dependencies are importable in every supported environment.
    assert by_name["gdsfactory"].status == FOUND
    assert by_name["LangGraph"].status == FOUND
    # Licence-bound bridges are never guessed.
    assert by_name["CST Python Bridge"].status == NOT_PROBED
    summary = summarize_inventory(probes)
    assert summary["total"] == 100 and sum(summary["by_status"].values()) == 100
    assert set(summary["by_pillar"]) == {str(i) for i in range(1, 11)}


def test_missing_executable_is_missing_not_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.delenv("TEXTLAYOUT_PALACE", raising=False)
    target = next(t for t in load_targets() if t.name == "AWS Palace")
    probe = probe_target(target, load_probe_specs()[target.id], roots=[tmp_path])
    assert probe.status == MISSING
    assert probe.kind == "executable"
    assert "not located" in probe.detail


def test_executable_found_under_cache_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.delenv("TEXTLAYOUT_JOSIM", raising=False)
    cache = tmp_path / "textlayout-josim" / "bin"
    cache.mkdir(parents=True)
    binary = cache / "josim-cli"
    binary.write_text("#!/bin/sh\n", encoding="ascii")
    binary.chmod(0o755)
    target = next(t for t in load_targets() if t.name == "JoSIM")
    probe = probe_target(
        target, load_probe_specs()[target.id], roots=[tmp_path / "textlayout-josim"]
    )
    assert probe.status == FOUND
    assert probe.path == str(binary)


def test_env_var_pointing_nowhere_is_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEXTLAYOUT_NGSPICE", str(tmp_path / "definitely-missing"))
    target = next(t for t in load_targets() if t.name == "ngspice")
    probe = probe_target(target, load_probe_specs()[target.id], roots=[tmp_path])
    assert probe.status == BROKEN
    assert "TEXTLAYOUT_NGSPICE" in probe.detail


def test_module_import_failure_is_broken(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "broken_textlayout_probe_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("raise RuntimeError('native extension exploded')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    target = load_targets()[0]
    spec = ToolProbeSpec(target_id=target.id, modules=("broken_textlayout_probe_pkg",))
    located = probe_target(target, spec, roots=[tmp_path])
    assert located.status == FOUND and "located" in located.detail
    imported = probe_target(target, spec, import_modules=True, roots=[tmp_path])
    assert imported.status == BROKEN
    assert "RuntimeError" in imported.detail


def test_cache_roots_include_tools_and_home_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEXTLAYOUT_TOOLS_DIR", str(tmp_path / "tools"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    (tmp_path / "cache" / "textlayout-palace").mkdir(parents=True)
    (tmp_path / "cache" / "textlayout-openems").mkdir(parents=True)
    (tmp_path / "cache" / "unrelated").mkdir(parents=True)
    roots = tool_cache_roots()
    assert roots[0] == tmp_path / "tools"
    assert [root.name for root in roots[1:]] == ["textlayout-openems", "textlayout-palace"]


def test_doctor_embeds_inventory_without_changing_pass_fail(tmp_path: Path) -> None:
    from textlayout.doctor import render_text, run_doctor

    report = run_doctor(output_dir=tmp_path / "probe")
    payload = report.to_dict()
    assert payload["integration_inventory"]["total"] == 100
    assert all(entry["execution_verified"] is False for entry in payload["integration_targets"])
    text = render_text(report)
    assert "[Integration catalog: 100 targets" in text
    assert "not execution evidence" in text
    # Catalog probes are informational only.
    quiet = run_doctor(output_dir=tmp_path / "probe2", probe_catalog=False)
    assert quiet.ok == report.ok
    assert quiet.to_dict()["integration_inventory"]["total"] == 0
