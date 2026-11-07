"""End-to-end tests for Priority 8: Full EPR to Circuit Hamiltonian Chain."""

from __future__ import annotations

import json
import math
from pathlib import Path

import klayout.db as kdb
import pytest

from textlayout.evidence.contract import EvidenceStatus
from textlayout.models import Geometry, rectangle
from textlayout.quantum import (
    JunctionModel,
    geometry_from_gds,
    run_field_to_qubit_pipeline,
)
from textlayout.quantum.epr import REPORT_BEGIN, REPORT_END, scqubits_available


def _create_sample_gds(path: Path) -> Path:
    layout = kdb.Layout()
    top = layout.create_cell("TRANSMON_CHIP")
    metal_layer = layout.insert_layer(kdb.LayerInfo(1, 0))
    # Add a transmon capacitor pad
    top.shapes(metal_layer).insert(kdb.Box(-50000, -20000, 50000, 20000))
    path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(path))
    return path


def test_geometry_from_gds(tmp_path: Path) -> None:
    gds_path = _create_sample_gds(tmp_path / "chip.gds")
    geom = geometry_from_gds(gds_path)
    assert geom.name == "TRANSMON_CHIP"
    assert len(geom.polygons) == 1
    bbox = geom.bbox()
    assert bbox.xmin == pytest.approx(-50.0)
    assert bbox.xmax == pytest.approx(50.0)
    assert bbox.ymin == pytest.approx(-20.0)
    assert bbox.ymax == pytest.approx(20.0)


def _setup_palace_postpro(out_dir: Path, ej_ghz: float, ec_ghz: float) -> Path:
    postpro = out_dir / "postpro"
    postpro.mkdir(parents=True, exist_ok=True)
    f_lin = math.sqrt(8.0 * ej_ghz * ec_ghz)

    # 1. eig.csv: eigenmode frequency and quality factor
    (postpro / "eig.csv").write_text(
        "m,Re{f} (GHz),Im{f} (GHz),Q,Error (Bkwd.),Error (Abs.)\n"
        f"1,{f_lin:.8f},1e-6,1.5e6,0,0\n"
        "2,7.50000000,1e-6,2.0e6,0,0\n",
        encoding="utf-8",
    )

    # 2. domain-E.csv: electric and magnetic energy participation per domain
    (postpro / "domain-E.csv").write_text(
        "m,E_elec (J),E_mag (J),E_cap (J),E_ind (J),E_elec[1] (J),p_elec[1],E_mag[1] (J),p_mag[1],E_elec[2] (J),p_elec[2],E_mag[2] (J),p_mag[2]\n"
        "1,1.0e-12,2.0e-13,0,8.0e-13,9.0e-13,0.90,1.5e-13,0.75,1.0e-13,0.10,5.0e-14,0.25\n"
        "2,1.0e-12,1.0e-12,0,1.0e-14,5.0e-13,0.50,5.0e-13,0.50,5.0e-13,0.50,5.0e-13,0.50\n",
        encoding="utf-8",
    )

    # 3. port-EPR.csv: junction port participation ratio p_mj
    # In transmon limit, mode 1 participates predominantly in junction 1: p_11 = 1.0
    (postpro / "port-EPR.csv").write_text(
        "m,p[1]\n1,1.000000\n2,0.005000\n",
        encoding="utf-8",
    )
    return postpro


def test_full_field_to_qubit_pipeline_transmon_chain(tmp_path: Path) -> None:
    ej_ghz = 20.0
    ec_ghz = 0.25
    gds_path = _create_sample_gds(tmp_path / "transmon.gds")
    sim_dir = tmp_path / "sim"
    _setup_palace_postpro(sim_dir, ej_ghz, ec_ghz)

    report_path = tmp_path / "report.md"
    report_path.write_text(
        "# Preliminary Report\n\nLayout generation verified.\n", encoding="utf-8"
    )

    junctions = [JunctionModel(name="J1", josephson_energy_ghz=ej_ghz, port_index=1)]
    res = run_field_to_qubit_pipeline(
        gds_path=gds_path,
        junctions=junctions,
        output_dir=sim_dir,
        report_path=report_path,
        execute_solver=False,
        cross_check_scqubits=True,
    )

    # Status check
    assert res.status == EvidenceStatus.SIMULATION_EXECUTED
    assert res.geometry_name == "TRANSMON_CHIP"
    assert res.e_j_ghz == pytest.approx(ej_ghz)
    assert res.e_c_ghz == pytest.approx(ec_ghz, rel=1e-3)

    # Anharmonicity alpha ~ -E_C in the transmon regime
    assert res.anharmonicity_ghz == pytest.approx(-ec_ghz, rel=1e-3)
    assert res.transmon_regime_valid is True

    # scqubits exact transmon diagonalization agreement check (< 0.5% error)
    if scqubits_available():
        assert res.scqubits_agreement_pass is True
        assert res.quantum_analysis.scqubits_cross_check is not None
        dev = res.quantum_analysis.scqubits_cross_check.f01_deviation_percent
        assert dev is not None and dev < 0.5

    # Verification of quantum_analysis.json persistence
    assert res.analysis_path is not None and res.analysis_path.is_file()
    payload = json.loads(res.analysis_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "textlayout.quantum-analysis.v1"
    assert payload["status"] == "SIMULATION_EXECUTED"
    assert "chi_matrix_ghz" in payload

    # Verification of report embedding
    assert res.report_path is not None and res.report_path.is_file()
    report_text = res.report_path.read_text(encoding="utf-8")
    assert REPORT_BEGIN in report_text
    assert REPORT_END in report_text
    assert "## Quantum (EPR) analysis" in report_text
    assert "Cross-Kerr chi (GHz)" in report_text


def test_field_to_qubit_pipeline_honest_missing_solver(tmp_path: Path) -> None:
    empty_dir = tmp_path / "no_solver"
    geom = Geometry("empty_pad", polygons=(rectangle("metal", 0, 0, 10, 10),))
    res = run_field_to_qubit_pipeline(
        geometry=geom,
        output_dir=empty_dir,
        execute_solver=False,
    )
    # Never fake or assume simulation convergence
    assert res.status == EvidenceStatus.SKIPPED_SOLVER_ABSENT
    assert res.transmon_regime_valid is False
    assert res.scqubits_agreement_pass is False
