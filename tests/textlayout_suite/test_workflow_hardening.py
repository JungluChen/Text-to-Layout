from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_RE = re.compile(r"\buses:\s*[^\s@]+@(?P<ref>[^\s#]+)")


def test_all_github_actions_are_pinned_to_immutable_commits() -> None:
    unpinned: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for match in ACTION_RE.finditer(text):
            if not re.fullmatch(r"[0-9a-f]{40}", match.group("ref")):
                unpinned.append(f"{workflow.name}: {match.group(0)}")
    assert unpinned == []


def test_workflows_and_dependabot_configuration_parse_as_yaml() -> None:
    for path in [*sorted(WORKFLOWS.glob("*.yml")), ROOT / ".github" / "dependabot.yml"]:
        assert isinstance(yaml.safe_load(path.read_text(encoding="utf-8")), dict)


def test_nightly_upload_is_fail_closed_and_points_to_deterministic_root() -> None:
    nightly = (WORKFLOWS / "nightly.yml").read_text(encoding="utf-8")
    assert "path: out/nightly" in nightly
    assert "if-no-files-found: error" in nightly
    assert "scripts/generate_nightly_manifest.py" in nightly
    assert "scripts/build_canonical_evidence.py --check" in nightly
    assert "scripts/render_showcase_artifacts.py --check" in nightly


def test_palace_smoke_and_product_benchmark_share_install_resolution() -> None:
    common = (ROOT / "scripts" / "external" / "_palace_common.py").read_text(
        encoding="utf-8"
    )
    capability = (
        ROOT / "src" / "textlayout" / "solvers" / "palace" / "capability.py"
    ).read_text(encoding="utf-8")
    workflow = (WORKFLOWS / "palace-integration.yml").read_text(encoding="utf-8")
    assert "validated_palace_install_record" in common
    assert "resolve_palace_install(_INSTALL_RECORD)" in capability
    assert "run_palace_smoke.py" in workflow
    assert "textlayout simulate palace-resonator" in workflow
