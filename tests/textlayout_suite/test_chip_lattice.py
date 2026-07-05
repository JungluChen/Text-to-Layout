"""Chip-level collision detection, Monte Carlo yield, optimizer, and CLI."""

from __future__ import annotations

import json
import random

import pytest

from textlayout.chip_lattice import (
    CollisionRules,
    CouplerEdge,
    QubitLattice,
    QubitNode,
    analyze_nominal,
    optimize_frequencies,
    run_chip_collision_yield,
    write_chip_optimize_report,
    write_chip_yield_report,
)
from textlayout.cli import main as cli_main


def _pair_lattice(
    f1: float = 5.000, f2: float = 5.010, sigma_mhz: float = 5.0, **rule_overrides
) -> QubitLattice:
    return QubitLattice(
        name="pair",
        nodes=[
            QubitNode(qubit_id="Q1", target_freq_ghz=f1, freq_sigma_mhz=sigma_mhz),
            QubitNode(qubit_id="Q2", target_freq_ghz=f2, freq_sigma_mhz=sigma_mhz),
        ],
        edges=[CouplerEdge(node_a="Q1", node_b="Q2", coupling_mhz=5.0)],
        rules=CollisionRules(**rule_overrides) if rule_overrides else CollisionRules(),
    )


def _grid_lattice(rows: int, cols: int, seed: int = 7) -> QubitLattice:
    rng = random.Random(seed)
    nodes = []
    edges = []
    for r in range(rows):
        for c in range(cols):
            qid = f"Q{r}_{c}"
            bin_freq = 5.0 if (r + c) % 2 == 0 else 5.3
            nodes.append(
                QubitNode(
                    qubit_id=qid,
                    target_freq_ghz=bin_freq + rng.uniform(-0.002, 0.002),
                    readout_freq_ghz=6.5 + rng.uniform(-0.01, 0.01),
                    freq_sigma_mhz=8.0,
                )
            )
    for r in range(rows):
        for c in range(cols):
            qid = f"Q{r}_{c}"
            if c + 1 < cols:
                edges.append(CouplerEdge(node_a=qid, node_b=f"Q{r}_{c + 1}", coupling_mhz=8.0))
            if r + 1 < rows:
                edges.append(CouplerEdge(node_a=qid, node_b=f"Q{r + 1}_{c}", coupling_mhz=8.0))
    return QubitLattice(name=f"{rows}x{cols}_grid", nodes=nodes, edges=edges)


class TestLatticeSchema:
    def test_duplicate_qubit_id_rejected(self) -> None:
        with pytest.raises(Exception):
            QubitLattice(
                name="bad",
                nodes=[
                    QubitNode(qubit_id="Q1", target_freq_ghz=5.0, freq_sigma_mhz=5.0),
                    QubitNode(qubit_id="Q1", target_freq_ghz=5.1, freq_sigma_mhz=5.0),
                ],
                edges=[],
            )

    def test_edge_to_unknown_node_rejected(self) -> None:
        with pytest.raises(Exception):
            QubitLattice(
                name="bad",
                nodes=[QubitNode(qubit_id="Q1", target_freq_ghz=5.0, freq_sigma_mhz=5.0)],
                edges=[CouplerEdge(node_a="Q1", node_b="Q2", coupling_mhz=5.0)],
            )

    def test_self_loop_edge_rejected(self) -> None:
        with pytest.raises(Exception):
            QubitLattice(
                name="bad",
                nodes=[QubitNode(qubit_id="Q1", target_freq_ghz=5.0, freq_sigma_mhz=5.0)],
                edges=[CouplerEdge(node_a="Q1", node_b="Q1", coupling_mhz=5.0)],
            )

    def test_neighbors_lookup(self) -> None:
        lattice = _pair_lattice()
        assert lattice.neighbors("Q1") == ["Q2"]
        assert lattice.neighbors("Q2") == ["Q1"]


class TestCollisionDetection:
    def test_close_qubit_qubit_pair_violates(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.010)  # 10 MHz apart, rule default 30 MHz
        report = analyze_nominal(lattice)
        assert not report.collision_free
        qubit_qubit = [f for f in report.findings if f.rule == "qubit_qubit"][0]
        assert qubit_qubit.violated
        assert qubit_qubit.detuning_mhz == pytest.approx(10.0, abs=1e-6)

    def test_well_separated_pair_is_collision_free(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.500)  # 500 MHz apart
        report = analyze_nominal(lattice)
        assert report.collision_free
        assert report.n_violations == 0

    def test_exact_threshold_boundary_is_not_violated(self) -> None:
        """Detuning exactly at the minimum required is compliant, not violated."""
        lattice = _pair_lattice(f1=5.000, f2=5.030, qubit_qubit_min_detuning_mhz=30.0)
        report = analyze_nominal(lattice)
        qubit_qubit = [f for f in report.findings if f.rule == "qubit_qubit"][0]
        assert not qubit_qubit.violated

    def test_qubit_readout_collision_detected(self) -> None:
        lattice = QubitLattice(
            name="readout_collision",
            nodes=[
                QubitNode(
                    qubit_id="Q1",
                    target_freq_ghz=6.500,
                    readout_freq_ghz=6.510,
                    freq_sigma_mhz=5.0,
                )
            ],
            edges=[],
        )
        report = analyze_nominal(lattice)
        readout_finding = [f for f in report.findings if f.rule == "qubit_readout"][0]
        assert readout_finding.violated  # 10 MHz apart, default rule 500 MHz

    def test_qubit_coupler_collision_detected(self) -> None:
        lattice = QubitLattice(
            name="coupler_collision",
            nodes=[
                QubitNode(qubit_id="Q1", target_freq_ghz=5.000, freq_sigma_mhz=5.0),
                QubitNode(qubit_id="Q2", target_freq_ghz=5.500, freq_sigma_mhz=5.0),
            ],
            edges=[CouplerEdge(node_a="Q1", node_b="Q2", coupler_freq_ghz=5.010, coupling_mhz=5.0)],
        )
        report = analyze_nominal(lattice)
        coupler_findings = [f for f in report.findings if f.rule == "qubit_coupler"]
        assert any(f.violated for f in coupler_findings)

    def test_no_edges_no_qubit_qubit_findings(self) -> None:
        lattice = QubitLattice(
            name="isolated",
            nodes=[QubitNode(qubit_id="Q1", target_freq_ghz=5.0, freq_sigma_mhz=5.0)],
            edges=[],
        )
        report = analyze_nominal(lattice)
        assert not any(f.rule == "qubit_qubit" for f in report.findings)
        assert report.collision_free


class TestChipCollisionYieldMonteCarlo:
    def test_deterministic_under_seed(self) -> None:
        lattice = _pair_lattice()
        r1 = run_chip_collision_yield(lattice, n_samples=500, seed=42)
        r2 = run_chip_collision_yield(lattice, n_samples=500, seed=42)
        assert r1.collision_free_pct == r2.collision_free_pct
        assert r1.risky_pairs == r2.risky_pairs

    def test_well_separated_lattice_has_high_collision_free_yield(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=6.000, sigma_mhz=5.0)
        result = run_chip_collision_yield(lattice, n_samples=1000, seed=1)
        assert result.collision_free_pct > 99.0

    def test_marginal_lattice_shows_risky_pair(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.020, sigma_mhz=10.0)
        result = run_chip_collision_yield(lattice, n_samples=2000, seed=1)
        assert len(result.risky_pairs) >= 1
        assert result.risky_pairs[0].collision_probability > 0

    def test_rejects_too_few_samples(self) -> None:
        with pytest.raises(ValueError):
            run_chip_collision_yield(_pair_lattice(), n_samples=10, seed=1)

    def test_forty_qubit_grid_runs_and_reports(self) -> None:
        lattice = _grid_lattice(rows=5, cols=8)  # 40 qubits
        assert len(lattice.nodes) == 40
        result = run_chip_collision_yield(lattice, n_samples=500, seed=42)
        assert 0.0 <= result.collision_free_pct <= 100.0
        assert result.nominal_report.n_nodes == 40

    def test_yield_ci_is_valid(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.015, sigma_mhz=10.0)
        result = run_chip_collision_yield(lattice, n_samples=1500, seed=3)
        low, high = result.collision_free_ci95_pct
        assert 0.0 <= low <= result.collision_free_pct <= high <= 100.0


class TestOptimizer:
    def test_already_collision_free_returns_unchanged(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=6.000)
        result = optimize_frequencies(lattice)
        assert result.converged
        assert result.proposals == []
        assert result.iterations == 0

    def test_resolves_a_simple_collision_within_bound(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.010)
        result = optimize_frequencies(lattice, max_retune_mhz=100.0, step_mhz=5.0)
        assert result.before.n_violations == 1
        assert result.converged
        assert result.after.collision_free

    def test_respects_max_retune_bound(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.010)
        result = optimize_frequencies(lattice, max_retune_mhz=5.0, step_mhz=1.0)
        for proposal in result.proposals:
            delta_mhz = abs(proposal.proposed_freq_ghz - proposal.original_freq_ghz) * 1e3
            assert delta_mhz <= 5.0 + 1e-6

    def test_reports_honest_nonconvergence_when_bound_too_tight(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.010)
        result = optimize_frequencies(lattice, max_retune_mhz=2.0, step_mhz=1.0)
        assert not result.converged
        assert not result.after.collision_free

    def test_optimizer_never_increases_penalty_relative_to_before(self) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.010)
        result = optimize_frequencies(lattice, max_retune_mhz=100.0, step_mhz=5.0)
        assert result.after.n_violations <= result.before.n_violations


class TestReportsAndCLI:
    def test_write_chip_yield_report_artifacts(self, tmp_path) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.010, sigma_mhz=10.0)
        result = run_chip_collision_yield(lattice, n_samples=500, seed=1)
        files = write_chip_yield_report(result, tmp_path)
        assert set(files) == {"json", "markdown", "collision_matrix"}
        payload = json.loads((tmp_path / "chip_yield_report.json").read_text(encoding="utf-8"))
        assert payload["lattice_name"] == "pair"
        csv_text = (tmp_path / "collision_matrix.csv").read_text(encoding="utf-8")
        assert "node_a,node_b,rule,collision_probability" in csv_text

    def test_write_chip_optimize_report_artifacts(self, tmp_path) -> None:
        lattice = _pair_lattice(f1=5.000, f2=5.010)
        result = optimize_frequencies(lattice, max_retune_mhz=100.0, step_mhz=5.0)
        files = write_chip_optimize_report(result, tmp_path)
        assert set(files) == {"json", "markdown"}
        assert (tmp_path / "chip_optimize_report.md").is_file()

    def test_cli_chip_analyze(self, tmp_path, capsys) -> None:
        lattice_path = tmp_path / "lattice.json"
        lattice_path.write_text(
            _pair_lattice(f1=5.000, f2=5.010).model_dump_json(), encoding="utf-8"
        )
        code = cli_main(
            [
                "chip",
                "analyze",
                str(lattice_path),
                "--n-samples",
                "500",
                "--seed",
                "1",
                "--out",
                str(tmp_path / "evidence"),
            ]
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["lattice_name"] == "pair"
        assert (tmp_path / "evidence" / "collision_matrix.csv").is_file()

    def test_cli_chip_analyze_strict_exits_nonzero_on_collision(self, tmp_path, capsys) -> None:
        lattice_path = tmp_path / "lattice.json"
        lattice_path.write_text(
            _pair_lattice(f1=5.000, f2=5.010).model_dump_json(), encoding="utf-8"
        )
        code = cli_main(
            [
                "chip",
                "analyze",
                str(lattice_path),
                "--n-samples",
                "500",
                "--strict",
            ]
        )
        assert code == 2
        capsys.readouterr()

    def test_cli_chip_optimize(self, tmp_path, capsys) -> None:
        lattice_path = tmp_path / "lattice.json"
        lattice_path.write_text(
            _pair_lattice(f1=5.000, f2=5.010).model_dump_json(), encoding="utf-8"
        )
        code = cli_main(
            [
                "chip",
                "optimize",
                str(lattice_path),
                "--max-retune-mhz",
                "100",
                "--step-mhz",
                "5",
                "--out",
                str(tmp_path / "evidence"),
            ]
        )
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["after"]["schema_version"]
        assert (tmp_path / "evidence" / "chip_optimize_report.md").is_file()
