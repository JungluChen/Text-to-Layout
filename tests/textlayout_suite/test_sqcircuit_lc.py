"""Protect explicit physical inputs and the prepared-only evidence boundary."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from textlayout.evidence.contract import EvidenceStatus
from textlayout.external.sqcircuit_lc import SQcircuitLCRequest, prepare_sqcircuit_lc


INPUTS = {"capacitance_f": 1e-13, "inductance_h": 1e-7, "branch_capacitance_f": 1e-20}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, 0.0, True, "1e-20"])
def test_reject_invalid_branch(value: object) -> None:
    with pytest.raises(ValidationError):
        SQcircuitLCRequest.model_validate({**INPUTS, "branch_capacitance_f": value})


def test_branch_is_required_and_unknown_topology_rejected() -> None:
    with pytest.raises(ValidationError):
        SQcircuitLCRequest.model_validate({"capacitance_f": 1e-13, "inductance_h": 1e-7})
    with pytest.raises(ValidationError):
        SQcircuitLCRequest.model_validate({**INPUTS, "junction": 1})


def test_preparation_is_repeatable_and_preserves_existing_evidence(tmp_path: Path) -> None:
    request = SQcircuitLCRequest.model_validate(INPUTS)
    first = prepare_sqcircuit_lc(request, output_dir=tmp_path / "first")
    second = prepare_sqcircuit_lc(request, output_dir=tmp_path / "repeat")
    raw = Path(first.input_path).read_bytes()
    assert raw == Path(second.input_path).read_bytes()
    assert first.input_sha256 == hashlib.sha256(raw).hexdigest() == second.input_sha256
    assert first.status == EvidenceStatus.SIMULATION_INPUT_PREPARED
    assert "quantities" not in first.model_dump()
    assert json.loads(raw)["request"] == INPUTS
    with pytest.raises(FileExistsError):
        prepare_sqcircuit_lc(request, output_dir=tmp_path / "first")
    assert Path(first.input_path).read_bytes() == raw
