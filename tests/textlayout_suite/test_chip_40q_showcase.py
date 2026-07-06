"""Sprint 4: the 40-qubit synthetic collision-yield showcase.

Covers the YAML lattice input path, seeded reproducibility, the
retune_proposal.json artifact, provenance/honesty blocks in every chip
report, and the end-to-end example script.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

from textlayout.chip_lattice import (
    QubitLattice,
    optimize_frequencies,
    run_chip_collision_yield,
    write_chip_optimize_report,
    write_chip_yield_report,
)
from textlayout.cli import _load_lattice
from textlayout.cli import main as cli_main

REPO_ROOT = Path(__file__).resolve().parents[2]
LATTICE_YAML = REPO_ROOT / "examples" / "chip_lattices" / "40q_synthetic.yaml"


def _lattice() -> QubitLattice:
    return QubitLattice.model_validate(
        yaml.safe_load(LATTICE_YAML.read_text(encoding="utf-8"))
    )


class TestYamlLattice:
    def test_cli_loader_accepts_yaml(self) -> None:
        lattice = _load_lattice(str(LATTICE_YAML))
        assert len(lattice.nodes) == 40
        assert len(lattice.edges) == 67  # 5x8 grid: 5*7 + 4*8

    def test_lattice_carries_all_required_fields(self) -> None:
        lattice = _lattice()
        node = lattice.nodes[0]
        assert node.readout_freq_ghz is not None
        assert node.anharmonicity_mhz == -200.0
        assert node.freq_sigma_mhz > 0
        assert all(edge.coupler_freq_ghz is not None for edge in lattice.edges)
        rules = lattice.rules
        assert rules.two_photon_min_detuning_mhz > 0  # higher-order hook present
        assert rules.charge_parity_min_detuning_mhz > 0

    def test_yaml_file_declares_synthetic_and_not_fab_ready(self) -> None:
        text = LATTICE_YAML.read_text(encoding="utf-8")
        assert "SYNTHETIC_EXAMPLE" in text
        assert "NOT_FABRICATION_READY" in text

    def test_cli_chip_analyze_accepts_yaml(
        self, tmp_path: Path, capsys
    ) -> None:
        exit_code = cli_main(
            [
                "chip",
                "analyze",
                str(LATTICE_YAML),
                "--seed",
                "1234",
                "--n-samples",
                "150",
                "--out",
                str(tmp_path),
            ]
        )
        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert (tmp_path / "collision_matrix.csv").is_file()
        assert payload["seed"] == 1234


class TestSeededReproducibility:
    def test_same_seed_same_yield(self) -> None:
        lattice = _lattice()
        a = run_chip_collision_yield(lattice, n_samples=150, seed=77)
        b = run_chip_collision_yield(lattice, n_samples=150, seed=77)
        assert a.collision_free_pct == b.collision_free_pct
        assert [(p.node_a, p.node_b, p.collision_probability) for p in a.risky_pairs] == [
            (p.node_a, p.node_b, p.collision_probability) for p in b.risky_pairs
        ]


class TestRetuneProposalArtifact:
    def test_retune_proposal_json_written_and_honest(self, tmp_path: Path) -> None:
        lattice = _lattice()
        result = optimize_frequencies(lattice, max_retune_mhz=300.0)
        files = write_chip_optimize_report(result, tmp_path)
        proposal = json.loads(
            Path(files["retune_proposal"]).read_text(encoding="utf-8")
        )
        assert proposal["schema"] == "textlayout.retune-proposal.v1"
        # The deliberate placement errors must be found and fixed.
        assert proposal["violations_before"] > 0
        assert proposal["violations_after"] < proposal["violations_before"]
        assert proposal["proposals"], "expected concrete retune proposals"
        for item in proposal["proposals"]:
            assert abs(item["delta_mhz"]) <= 300.0 + 1e-9
        assert proposal["provenance"]["fabrication_readiness"] == "NOT_FABRICATION_READY"


class TestProvenanceInReports:
    def test_yield_report_carries_provenance(self, tmp_path: Path) -> None:
        lattice = _lattice()
        result = run_chip_collision_yield(lattice, n_samples=150, seed=1)
        files = write_chip_yield_report(result, tmp_path)
        report = json.loads(Path(files["json"]).read_text(encoding="utf-8"))
        prov = report["provenance"]
        assert prov["status"] == "SYNTHETIC_EXAMPLE"
        assert prov["evidence_class"] == "ANALYTICAL_ONLY"
        assert prov["fabrication_readiness"] == "NOT_FABRICATION_READY"
        assert len(prov["pdk_provenance"]["file_hash_sha256"]) == 64
        markdown = Path(files["markdown"]).read_text(encoding="utf-8")
        assert "NOT_FABRICATION_READY" in markdown
        assert "undirected" in markdown  # collision-pair directionality documented


class TestShowcaseScript:
    def test_example_07_runs_end_to_end(self, tmp_path: Path, capsys) -> None:
        spec = importlib.util.spec_from_file_location(
            "example_07_40q", REPO_ROOT / "examples" / "07_40q_chip_collision_yield.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["example_07_40q"] = module
        spec.loader.exec_module(module)
        exit_code = module.main(["--out", str(tmp_path), "--n-samples", "150"])
        assert exit_code == 0
        summary = json.loads(capsys.readouterr().out)
        assert summary["status"] == "SYNTHETIC_EXAMPLE"
        assert summary["fabrication_readiness"] == "NOT_FABRICATION_READY"
        # Honesty of the improvement claim: after <= before, and the retuned
        # Monte Carlo yield must not be lower than the baseline's.
        assert summary["retune"]["violations_after"] <= summary["retune"]["violations_before"]
        if summary["retuned_collision_free_yield_pct"] is not None:
            assert (
                summary["retuned_collision_free_yield_pct"]
                >= summary["baseline"]["collision_free_yield_pct"]
            )
        for name in (
            "chip_yield_report.json",
            "chip_yield_report.md",
            "collision_matrix.csv",
            "retune_proposal.json",
        ):
            assert (tmp_path / name).is_file(), name
