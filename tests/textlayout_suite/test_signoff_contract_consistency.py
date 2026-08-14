"""Normative documents and the public evaluator must describe one contract."""

from __future__ import annotations

from pathlib import Path

from textlayout.signoff import SIGNOFF_LEVELS, SIGNOFF_SCHEMA, SignoffResult

ROOT = Path(__file__).resolve().parents[2]


def test_normative_sources_require_two_independent_solvers_for_level_5() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    criteria = (ROOT / "SIGNOFF_CRITERIA.md").read_text(encoding="utf-8")
    product_docs = (ROOT / "docs" / "signoff_levels.md").read_text(encoding="utf-8")

    assert "≥2 solvers + agreement" in agents
    assert "independent solver families" in criteria
    assert "independent solver families" in product_docs
    assert "same design hash" in criteria
    assert "design hash, analysis scope, and quantity" in product_docs


def test_public_result_schema_is_v2_and_exposes_agreement_provenance() -> None:
    schema = SignoffResult.model_json_schema()
    properties = schema["properties"]
    assert SIGNOFF_SCHEMA == "textlayout.signoff.v2"
    assert properties["schema_version"]["default"] == SIGNOFF_SCHEMA
    assert "executed_solver_ids" in properties
    assert "executed_solver_evidence_ids" in properties
    assert "executed_solver_families" in properties
    assert "solver_agreement_passed" in properties
    assert "solver_agreement_status" in properties
    assert "passed_level_5_physics_signoff" in properties
    assert "passed_level_6_measurement_calibrated" in properties


def test_documented_level_tables_are_generated_from_evaluator_constants() -> None:
    import importlib.util

    script = ROOT / "scripts" / "generate_signoff_docs.py"
    spec = importlib.util.spec_from_file_location("generate_signoff_docs", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert len(SIGNOFF_LEVELS) == 8
    for path, include_no_geometry in (
        (ROOT / "SIGNOFF_CRITERIA.md", False),
        (ROOT / "docs" / "signoff_levels.md", True),
    ):
        content = path.read_text(encoding="utf-8")
        assert module.replace_table(content, module.table(include_no_geometry=include_no_geometry)) == content
