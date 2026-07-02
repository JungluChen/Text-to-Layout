"""Product-level acceptance tests for README and documentation promises.

These guard reader-facing trust: well-formed benchmark tables, no ambiguous PASS
claims, an honest clean-room doc, an explicit HTTPS requirement for public GPT
Actions, and JSON (not HTML) API errors.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from textlayout.backend import create_app

REPO = Path(__file__).resolve().parents[2]
README = (REPO / "README.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace (and blockquote markers) so assertions survive
    markdown line wrapping."""
    stripped = [re.sub(r"^\s*>\s?", "", line) for line in text.splitlines()]
    return " ".join(" ".join(stripped).split())


def _markdown_tables(text: str) -> list[list[str]]:
    """Return each markdown table as a list of its raw row lines."""
    tables: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            current.append(line.strip())
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _columns(row: str) -> int:
    # A markdown row "| a | b | c |" has cells between the outer pipes.
    return len(row.strip().strip("|").split("|"))


# 1. Benchmark tables are well-formed (every row matches its header width).
def test_readme_benchmark_tables_well_formed() -> None:
    benchmark_tables = [
        t for t in _markdown_tables(README)
        if any("examples/benchmarks/" in row for row in t)
    ]
    assert benchmark_tables, "expected at least one benchmark table in README"
    for table in benchmark_tables:
        assert len(table) >= 3, "table needs header, separator, and a data row"
        header_cols = _columns(table[0])
        assert re.match(r"^\|[\s:\-|]+\|$", table[1]), "missing/!malformed separator row"
        for row in table[2:]:
            assert _columns(row) == header_cols, f"ragged row: {row}"


# 2. The README carries both an honest per-benchmark status table and the
# CI-validated component support matrix. (Originally this asserted MVP2's
# visual/engineering table split; the consolidated README serves the same
# intent with one 8-column benchmark table plus the support matrix.)
def test_readme_has_benchmark_and_support_tables() -> None:
    assert "## Layout Benchmarks" in README
    assert "Geometry Status | Simulation Status | Evidence Status | Fabrication Status" in README
    assert "## Component support matrix" in README


# 3. No ambiguous unqualified PASS on any benchmark line.
def test_readme_no_ambiguous_pass() -> None:
    ambiguous = re.compile(r"(?<!GEOMETRY )PASS")
    for line in README.splitlines():
        if "examples/benchmarks/" in line:
            assert not ambiguous.search(line), f"ambiguous PASS on: {line}"


# 4. README must not over-claim physics or fabrication readiness.
def test_readme_no_overclaim() -> None:
    assert "No benchmark in this repository is currently PHYSICS VERIFIED" in README
    # Public-plugin readiness must be explicitly disclaimed, not asserted.
    assert '**not** claimed to be "public ChatGPT plugin ready"' in _flat(README)


# 5. Clean-room verification doc exists and is honest.
def test_clean_room_doc_exists_and_is_honest() -> None:
    doc = (REPO / "CLEAN_ROOM_VERIFICATION.md").read_text(encoding="utf-8")
    assert "local CLI / API / plugin-style verification PASS" in doc
    # Must NOT claim a public deployment.
    assert "does **not** claim a public GPT Action deployment" in _flat(doc)


# 6. Public GPT Action doc states the HTTPS requirement explicitly.
def test_public_gpt_action_doc_states_https() -> None:
    doc = (REPO / "docs" / "public_gpt_action_deployment.md").read_text(encoding="utf-8")
    assert "public HTTPS" in doc
    assert "cannot reach" in doc and "localhost" in doc
    assert "local plugin-style ready" in doc.lower() or "local plugin-style" in doc


# 7. Artifact policy doc exists and documents determinism.
def test_artifact_policy_doc_exists() -> None:
    doc = (REPO / "docs" / "artifact_policy.md").read_text(encoding="utf-8")
    assert "no git diff" in doc
    assert "layout_json_sha256" in doc
    assert "gds2_write_timestamps" in doc


# 8. README points at the new trust artifacts.
def test_readme_links_trust_artifacts() -> None:
    for target in (
        "CLEAN_ROOM_VERIFICATION.md",
        "docs/artifact_policy.md",
        "docs/public_gpt_action_deployment.md",
        "examples/acceptance/",
    ):
        assert target in README, f"README should reference {target}"


# 9. OpenAPI schema is valid JSON via the app.
def test_openapi_schema_is_valid_json() -> None:
    client = TestClient(create_app())
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].split(";")[0] == "application/json"
    body = resp.json()
    assert body["openapi"].startswith("3.")


# 10. API errors are JSON, not HTML error pages.
def test_api_errors_are_json_not_html() -> None:
    client = TestClient(create_app())
    # Unknown component -> structured JSON error, not an HTML 500 page.
    resp = client.post("/layout/verify", json={"component": "NotAThing", "parameters": {}})
    assert resp.headers["content-type"].split(";")[0] == "application/json"
    assert resp.status_code >= 400
    assert "error" in resp.json() or "detail" in resp.json()
