from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_docs_links.py"


def _module():
    spec = importlib.util.spec_from_file_location("check_docs_links", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_repository_document_links_are_valid() -> None:
    assert _module().broken_links(ROOT / "docs") == []


def test_broken_current_link_fails_but_classified_history_is_excluded(tmp_path: Path) -> None:
    module = _module()
    (tmp_path / "current.md").write_text("[missing](nope.md)\n", encoding="utf-8")
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "snapshot.md").write_text("[also missing](gone.md)\n", encoding="utf-8")
    assert module.broken_links(tmp_path) == ["current.md: missing local link target 'nope.md'"]
