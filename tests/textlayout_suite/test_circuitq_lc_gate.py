"""Synthetic gate tests are not execution evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "circuitq_gate", ROOT / "scripts/check_circuitq_lc.py"
)
assert spec and spec.loader
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
PLAN = json.loads(bench.PLAN.read_text())


def rows() -> list[dict]:
    pairs = [(d, PLAN["half_domain_sigma"]) for d in PLAN["dimensions"]]
    pairs += [(PLAN["expanded_dimension"], PLAN["expanded_half_domain_sigma"])]
    return [
        dict(
            dimension=d,
            resolved_dimension=d,
            half_domain_sigma=e,
            frequency_hz=2e9,
            anharmonicity_hz=0.0,
            scaled_residual=1e-16,
            hermiticity_relative=0.0,
            matrix_similarity_relative=1e-14,
        )
        for d, e in pairs
    ]


def test_immutable_plan() -> None:
    assert hashlib.sha256(bench.PLAN.read_bytes()).hexdigest() == bench.PLAN_SHA256
    assert bench.assess(rows(), PLAN, 2e9)[1]


@pytest.mark.parametrize(
    "key,value,index",
    [
        ("frequency_hz", 2.1e9, 2),
        ("frequency_hz", 2.1e9, 1),
        ("anharmonicity_hz", 1e6, 2),
        ("frequency_hz", 2.01e9, 3),
        ("scaled_residual", 1e-7, 0),
        ("hermiticity_relative", 1e-4, 0),
    ],
)
def test_each_numerical_condition_rejects(key: str, value: float, index: int) -> None:
    data = rows()
    data[index][key] = value
    assert not bench.assess(data, PLAN, 2e9)[1]


@pytest.mark.parametrize(
    "key,value",
    [
        ("frequency_hz", float("nan")),
        ("frequency_hz", -1),
        ("scaled_residual", -1),
        ("matrix_similarity_relative", 1e-8),
        ("resolved_dimension", 400),
    ],
)
def test_invalid_output_rejects(key: str, value: float) -> None:
    data = rows()
    data[0][key] = value
    with pytest.raises(ValueError):
        bench.assess(data, PLAN, 2e9)


def test_missing_domain_rejects() -> None:
    with pytest.raises(ValueError):
        bench.assess(rows()[:-1], PLAN, 2e9)
