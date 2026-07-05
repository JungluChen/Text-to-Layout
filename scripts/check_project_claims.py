"""Project-wide claim consistency checker.

Distinct from `scripts/validate_readme_claims.py` (which audits the README's
showcase/benchmark tables against committed artifacts in deep detail). This
script catches *cross-document* drift: README vs status docs vs package
metadata vs the showcase index's own ground truth. Fails non-zero (CI-safe)
on any of:

1. README claims `PHYSICS_VERIFIED` for a showcase example that
   `examples/showcase/index.json` does not back (or vice versa).
2. README describes a solver as executed for an example index.json marks
   `solver_executed: false`.
3. `pyproject.toml`'s version conflicts with a version explicitly stated in
   a status doc (`IMPLEMENTATION_REPORT.md`, `CHANGELOG.md`'s latest entry).
4. Fabrication-ready language appears (a positive claim, not a negated
   "NOT_FABRICATION_READY"/"not fabrication-ready") while no PDK in the repo
   is `foundry_validated: true`.
5. `pyproject.toml`'s description contradicts the documented architecture
   (`textlayout` = product path, `text_to_gds` = frozen legacy).

Usage:
    python scripts/check_project_claims.py
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: A "fabrication ready" claim must be negated by one of these on the same
#: line (or immediately adjacent) to not count as a positive claim.
#: Word-boundary regex so markdown emphasis ("**no**") doesn't defeat detection.
_NEGATION_RE = re.compile(r"\b(not|no|nothing|never|isn't|aren't)\b", re.I)

#: A vocabulary/legend row that merely *defines* the label, e.g.
#: "| **FABRICATION READY** | Process-specific DRC ... complete |" — the
#: phrase is (ignoring markdown bold markers) the entire first table cell.
legend_row_re = re.compile(r"^\s*\|\s*\*{0,2}fabrication[- ]ready\*{0,2}\s*\|", re.I)

_STATUS_DOCS_WITH_VERSION = ("IMPLEMENTATION_REPORT.md",)


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def _load_showcase_index() -> list[dict]:
    index_path = ROOT / "examples" / "showcase" / "index.json"
    if not index_path.is_file():
        return []
    data = json.loads(index_path.read_text(encoding="utf-8"))
    examples = data.get("examples", [])
    return examples if isinstance(examples, list) else []


def check_physics_verified_and_execution_claims(errors: list[str]) -> None:
    """README per-example claims must agree with examples/showcase/index.json."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for example in _load_showcase_index():
        example_id = example.get("id")
        if not example_id:
            continue
        # Find the README table row for this example: it links to
        # examples/showcase/<id>/ somewhere on one line.
        row_match = re.search(
            rf"^\|.*examples/showcase/{re.escape(example_id)}/.*\|$",
            readme,
            re.M,
        )
        if not row_match:
            continue  # not every example needs a README row (index is the source of truth)
        row = row_match.group(0)
        index_says_verified = example.get("evidence_status") == "PHYSICS_VERIFIED"
        readme_says_verified = "PHYSICS_VERIFIED" in row
        if readme_says_verified and not index_says_verified:
            _fail(
                errors,
                f"{example_id}: README claims PHYSICS_VERIFIED but "
                f"examples/showcase/index.json evidence_status is "
                f"{example.get('evidence_status')!r}",
            )
        if index_says_verified and not readme_says_verified:
            _fail(
                errors,
                f"{example_id}: index.json says PHYSICS_VERIFIED but the README "
                "row does not mention it",
            )

        solver_executed = bool(example.get("solver_executed"))
        row_lower = row.lower()
        claims_executed = "executed" in row_lower or "physics_verified" in row_lower
        if claims_executed and not solver_executed:
            _fail(
                errors,
                f"{example_id}: README row implies solver execution but "
                f"index.json solver_executed=False (status="
                f"{example.get('simulation_status')!r})",
            )


def check_version_consistency(errors: list[str]) -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = str(pyproject["project"]["version"])

    for doc_name in _STATUS_DOCS_WITH_VERSION:
        doc_path = ROOT / doc_name
        if not doc_path.is_file():
            continue
        text = doc_path.read_text(encoding="utf-8")
        match = re.search(r"\*\*Version:\*\*\s*([0-9]+\.[0-9]+\.[0-9]+)", text)
        if match and match.group(1) != package_version:
            _fail(
                errors,
                f"{doc_name} states Version: {match.group(1)} but "
                f"pyproject.toml version is {package_version!r}",
            )

    changelog = ROOT / "CHANGELOG.md"
    if changelog.is_file():
        text = changelog.read_text(encoding="utf-8")
        match = re.search(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]", text, re.M)
        if match and match.group(1) != package_version:
            _fail(
                errors,
                f"CHANGELOG.md's latest release entry is [{match.group(1)}] but "
                f"pyproject.toml version is {package_version!r}",
            )


def check_fabrication_readiness_claims(errors: list[str]) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from textlayout.knowledge.technology_library import PDKS_DIR
    from textlayout.pdk import load_pdk

    any_foundry_validated = False
    for pdk_path in sorted(PDKS_DIR.glob("*.yaml")):
        try:
            pdk = load_pdk(pdk_path)
        except Exception:  # noqa: BLE001
            continue
        if pdk.foundry_validated:
            any_foundry_validated = True

    if any_foundry_validated:
        return  # a real foundry-validated PDK exists; positive claims may be legitimate

    docs_to_scan = ["README.md", "CURRENT_STATUS.md", "PROJECT_STATUS.md"]
    positive_claim_re = re.compile(r"fabrication[- ]ready", re.I)
    for doc_name in docs_to_scan:
        doc_path = ROOT / doc_name
        if not doc_path.is_file():
            continue
        for lineno, line in enumerate(doc_path.read_text(encoding="utf-8").splitlines(), 1):
            if legend_row_re.match(line):
                continue  # defines what the label means; not a claim about anything
            if _NEGATION_RE.search(line):
                continue  # negation anywhere on the line (before OR after the phrase)
            for match in positive_claim_re.finditer(line):
                _fail(
                    errors,
                    f"{doc_name}:{lineno}: unnegated 'fabrication-ready' claim with no "
                    f"foundry-validated PDK present: {line.strip()!r}",
                )


def check_textlayout_text_to_gds_roles(errors: list[str]) -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    description = str(pyproject["project"]["description"])
    if "textlayout" not in description:
        _fail(
            errors,
            "pyproject.toml description does not mention 'textlayout' as the "
            "product path — it must name which package is current.",
        )
    if "text_to_gds" in description and "legacy" not in description.lower():
        _fail(
            errors,
            "pyproject.toml description mentions text_to_gds without calling "
            "it legacy — this contradicts ARCHITECTURE.md's documented roles.",
        )

    architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    if "textlayout" not in architecture or "legacy" not in architecture.lower():
        _fail(
            errors,
            "ARCHITECTURE.md does not clearly state textlayout=product / "
            "text_to_gds=legacy roles.",
        )


def run_all_checks() -> list[str]:
    errors: list[str] = []
    check_physics_verified_and_execution_claims(errors)
    check_version_consistency(errors)
    check_fabrication_readiness_claims(errors)
    check_textlayout_text_to_gds_roles(errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    del argv
    errors = run_all_checks()
    if errors:
        print(f"Project claim check FAILED ({len(errors)} problem(s)):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Project claim check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
