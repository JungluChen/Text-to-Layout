"""Synthetic parser fixtures only; real pinned-data execution is retained separately."""
import hashlib
import json

import pytest

from textlayout.external.squadds_mcp import load_wm1_prior
from textlayout.verification.squadds_reference import ASSETS


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    rows = [{"contrib_info": {"name": "WM1"}, "measured_results": [{"H_params": [{
        f"qubit_{i}": {"F_res_GHz": 6.1, "F_01_GHz": 4.2, "Anharmocity_MHz": -153}
        for i in range(1, 7)
    }]}]}]

    def write(data):
        path = tmp_path / "synthetic.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setitem(ASSETS, "measured_device_database.json", {
            **ASSETS["measured_device_database.json"],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        return path
    return rows, write


def test_units_identity_and_no_promotion(dataset):
    rows, write = dataset
    path = write(rows)
    result = load_wm1_prior(path, "qubit_1").to_dict()
    assert result == load_wm1_prior(path, "qubit_1").to_dict()
    assert result["hamiltonian_parameters"] == {
        "resonator_frequency_hz": 6100000000.0,
        "qubit_frequency_hz": 4200000000.0,
        "anharmonicity_hz": -153000000.0,
    }
    assert result["evidence_status"] == "PRIOR_ONLY"
    assert result["physics_verified"] is False
    assert result["geometry_priors"] == {}
    metadata = result["dataset_metadata"]
    assert metadata["device_to_top_variant_mapping"] is None
    assert metadata["fields"]["anharmonicity_hz"]["source_field"] == "Anharmocity_MHz"
    assert metadata["upstream_package_executed"] is False


def test_unknown_device_and_modified_bytes_rejected(dataset):
    rows, write = dataset
    path = write(rows)
    with pytest.raises(ValueError, match="device_id"):
        load_wm1_prior(path, "qubit_7")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA-256"):
        load_wm1_prior(path, "qubit_1")


@pytest.mark.parametrize("value", [True, "6.1", None, float("nan"), float("inf"), 0, -1])
def test_invalid_frequency_rejected(dataset, value):
    rows, write = dataset
    rows[0]["measured_results"][0]["H_params"][0]["qubit_1"]["F_res_GHz"] = value
    with pytest.raises(ValueError):
        load_wm1_prior(write(rows), "qubit_1")


def test_ambiguous_contribution_and_missing_device_rejected(dataset):
    rows, write = dataset
    with pytest.raises(ValueError, match="exactly one"):
        load_wm1_prior(write(rows * 2), "qubit_1")
    del rows[0]["measured_results"][0]["H_params"][0]["qubit_6"]
    with pytest.raises(ValueError, match="six WM1"):
        load_wm1_prior(write(rows), "qubit_1")


def test_cli_json_and_read_only_source(dataset, capsys):
    from textlayout.cli import main
    rows, write = dataset
    path = write(rows)
    before = path.read_bytes()
    assert main(["squadds-prior", str(path), "--device", "qubit_2"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == load_wm1_prior(path, "qubit_2").to_dict()
    assert path.read_bytes() == before


def test_cli_missing_and_changed_source(dataset, capsys, tmp_path):
    from textlayout.cli import main
    assert main(["squadds-prior", str(tmp_path / "missing"), "--device", "qubit_1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"] == "FileNotFoundError"
    rows, write = dataset
    path = write(rows)
    path.write_bytes(b"changed")
    assert main(["squadds-prior", str(path), "--device", "qubit_1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "SHA-256" in json.loads(captured.err)["message"]


def test_cli_requires_explicit_valid_device():
    from textlayout.cli import main
    for args in (["squadds-prior", "unused"],
                 ["squadds-prior", "unused", "--device", "qubit_7"]):
        with pytest.raises(SystemExit) as caught:
            main(args)
        assert caught.value.code == 2
