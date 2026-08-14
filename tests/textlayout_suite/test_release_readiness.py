from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module(script: str):
    path = ROOT / "scripts" / script
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v030_metadata_and_changelog_are_consistent() -> None:
    checker = _module("check_release_consistency.py")
    assert checker.validate_release(tag="v0.3.0", root=ROOT) == []
    assert checker.validate_release(tag="v9.9.9", root=ROOT)


def test_release_metadata_has_distribution_hashes_and_source_commit(tmp_path: Path) -> None:
    generator = _module("generate_release_metadata.py")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "package.whl").write_bytes(b"wheel")
    sbom, provenance = generator.build_metadata(dist, root=ROOT)
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"
    assert provenance["subject"][0]["digest"]["sha256"] == generator.sha256_file(
        dist / "package.whl"
    )


def test_sdist_excludes_large_raw_fields_and_paper_pdfs() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"/**/openems_run/et"' in pyproject
    assert '"/**/openems_run/ht"' in pyproject
    assert '"/paper/*.pdf"' in pyproject
