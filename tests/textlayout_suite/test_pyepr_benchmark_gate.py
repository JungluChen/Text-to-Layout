"""Gate regressions use synthetic tables, never counted as solver evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "pyepr_benchmark", ROOT / "scripts/check_pyepr_charge_insensitive.py"
)
assert spec is not None and spec.loader is not None
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
PLAN = json.loads(bench.PLAN.read_text())


def table() -> dict:
    return {
        "fock": [dict(cutoff=n, f01_hz=6e9, alpha_hz=-150e6,
                      hamiltonian_f01_hz=6e9, hamiltonian_alpha_hz=-150e6)
                 for n in PLAN["fock_truncations"]],
        "reference": [dict(ng=ng, cutoff=n, f01_hz=6e9, alpha_hz=-150e6)
                      for ng in PLAN["charge_offsets"] for n in PLAN["charge_cutoffs"]],
    }


def test_plan_immutable_and_integer_inputs() -> None:
    assert hashlib.sha256(bench.PLAN.read_bytes()).hexdigest() == bench.PLAN_SHA256
    integer = PLAN["cases"][0]
    floating = {k: float(v) for k, v in integer.items()}
    assert bench.derived_inputs(integer) == bench.derived_inputs(floating)
    assert bench.derived_inputs(integer)[0] == 6.0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), complex(6e9, 1),
                                   complex(1, float("nan"))])
def test_reject_nonfinite_and_material_imaginary(value: complex) -> None:
    with pytest.raises(ValueError):
        bench.finite_real(value)


def test_roundoff_is_bounded() -> None:
    assert bench.finite_real(complex(6e9, 1e-20)) == 6e9
    assert bench.assess(table(), PLAN)[1]


@pytest.mark.parametrize("failure", ["fock", "reference", "spread", "difference", "units"])
def test_each_acceptance_condition_rejects(failure: str) -> None:
    data = table()
    if failure == "fock":
        data["fock"][-2]["f01_hz"] += 10
    elif failure == "reference":
        data["reference"][-2]["alpha_hz"] += 10
    elif failure == "spread":
        data["reference"][-1]["f01_hz"] += 1.5
    elif failure == "difference":
        for row in data["reference"]:
            row["alpha_hz"] += 3
    else:
        data["fock"][-1]["hamiltonian_f01_hz"] /= 1e9
    assert not bench.assess(data, PLAN)[1]


@pytest.mark.parametrize("collection", ["fock", "reference"])
def test_incomplete_or_nonfinite_samples_reject(collection: str) -> None:
    data = table()
    broken = copy.deepcopy(data)
    broken[collection].pop()
    with pytest.raises(ValueError):
        bench.assess(broken, PLAN)
    data[collection][0]["f01_hz"] = float("nan")
    with pytest.raises(ValueError):
        bench.assess(data, PLAN)
