from __future__ import annotations

import hashlib
import json
from pathlib import Path

from textlayout.cli import build_parser

ROOT = Path(__file__).resolve().parents[2]


def test_official_smoke_config_is_pinned_by_hash() -> None:
    root = ROOT / "external_tools" / "palace" / "smoke" / "eigenmode"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    payload = (root / manifest["config"]["path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == manifest["config"]["sha256"]
    assert manifest["palace_commit"] == "12d8069afb5aa9e169a17e303d735e120968e9f2"


def test_public_palace_command_parses() -> None:
    args = build_parser().parse_args(
        ["simulate", "palace-resonator", "--out", "out/palace_resonator"]
    )
    assert args.simulate_command == "palace-resonator"
    assert args.processes == 4


def test_public_palace_resume_and_status_flags_parse() -> None:
    args = build_parser().parse_args(
        [
            "simulate",
            "palace-resonator",
            "--out",
            "out/palace_resonator",
            "--status",
            "--resume",
            "--stage",
            "base_amr",
            "--from-stage",
            "mode_tracking",
        ]
    )
    assert args.status is True
    assert args.resume is True
    assert args.stage == "base_amr"
    assert args.from_stage == "mode_tracking"


def test_makefile_exposes_palace_lifecycle() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("setup-palace:", "check-palace:", "smoke-palace:", "benchmark-palace:"):
        assert target in text


def test_normal_ci_can_check_absent_palace() -> None:
    from textlayout.solvers.palace.capability import detect_palace

    capability = detect_palace(
        finder=lambda *args, **kwargs: None,
        probe_version=False,
    )
    assert capability.available is False
    assert "Palace was not found" in str(capability.unavailable_reason)
