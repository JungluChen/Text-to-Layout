"""Reference promotion rejects missing, modified and mismatched evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from textlayout.evidence.contract import EvidenceStatus, QuantityEvidence, PublicReferenceComparison
from textlayout.cli import build_parser
from textlayout.verification.squadds_reference import verified_asset


def proof(tmp_path):
    source = tmp_path / "published.json"
    source.write_text('{"value": 10}')
    output = tmp_path / "execution.json"
    output.write_text('{"value": 10.01}')
    declaration = tmp_path / "tolerance.json"
    declaration.write_text(json.dumps({"tolerance_percent": 1.0,
        "justification": "Synthetic contract test only; not a production numerical tolerance"}))
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(source_url="https://example.org/pinned", source_revision="a"*40,
        source_file=str(source), source_sha256=digest(source), source_selection="value",
        published_value=10, unit="GHz", library="synthetic-test", library_version="1",
        execution_output=str(output), execution_sha256=digest(output),
        tolerance_percent=1.0,
        tolerance_justification="Synthetic contract test only; not a production numerical tolerance",
        tolerance_source=str(declaration), tolerance_source_sha256=digest(declaration))


def record(data, **changes):
    kwargs = dict(quantity="frequency", target_value=10, target_unit="GHz",
        extracted_value=10.01, extracted_unit="GHz", error_percent=0.1,
        tolerance_percent=1, status=EvidenceStatus.REFERENCE_AGREED,
        solver="synthetic-test", parser="json", output_files=[data["execution_output"]],
        public_reference=data)
    kwargs.update(changes)
    return QuantityEvidence(**kwargs)


def test_agreement_and_mismatch(tmp_path):
    data = proof(tmp_path)
    assert record(data).is_physics_verified
    with pytest.raises(ValueError, match="reference mismatch"):
        record(data, extracted_value=11, error_percent=0)
    with pytest.raises(ValueError, match="pinned public"):
        record(data, public_reference=None)
    with pytest.raises(ValueError, match="matching units"):
        record(data, extracted_unit="MHz")


@pytest.mark.parametrize("field", ["source_file", "execution_output", "tolerance_source"])
def test_changed_provenance_rejected(tmp_path, field):
    data = proof(tmp_path)
    Path(data[field]).write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        PublicReferenceComparison(**data)


def test_tolerance_cannot_change_after_declaration(tmp_path):
    data = proof(tmp_path)
    data["tolerance_percent"] = 90
    with pytest.raises(ValueError, match="source declaration"):
        PublicReferenceComparison(**data)


def test_cli_reference_needs_no_repository_script():
    args = build_parser().parse_args(["verify", "--reference", "--offline"])
    assert args.reference and args.offline and args.spec is None


def test_reference_cache_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="Missing cached"):
        verified_asset("wm1.gds", tmp_path, offline=True)
    (tmp_path / "wm1.gds").write_bytes(b"modified")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verified_asset("wm1.gds", tmp_path, offline=True)
