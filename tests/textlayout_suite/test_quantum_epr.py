"""EPR quantisation: transmon limit, Palace ingestion, persistence, honest statuses."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from textlayout.evidence.contract import EvidenceStatus
from textlayout.quantum import (
    JunctionModel,
    ModeEnergy,
    analyze_palace_output,
    embed_in_report,
    epr_from_participations,
    modes_from_palace_output,
    render_quantum_summary,
    write_quantum_analysis,
)
from textlayout.quantum.epr import (
    REPORT_BEGIN,
    REPORT_END,
    josephson_energy_ghz_from_ic,
    josephson_energy_ghz_from_lj,
    scqubits_available,
    scqubits_transmon_cross_check,
)

EJ, EC = 20.0, 0.25
F_LIN = math.sqrt(8 * EJ * EC)


def _transmon(cross_check: bool = False):  # type: ignore[no-untyped-def]
    modes = [
        ModeEnergy(index=1, frequency_ghz=F_LIN, junction_participation={"J1": 1.0}),
        ModeEnergy(index=2, frequency_ghz=7.2, junction_participation={"J1": 0.01}),
    ]
    return epr_from_participations(
        modes, [JunctionModel(name="J1", josephson_energy_ghz=EJ)], cross_check=cross_check
    )


def test_junction_energy_conversions_agree() -> None:
    # L_J = Phi0 / (2 pi Ic): 20 nA -> 16.45 nH, both routes give the same E_J.
    ic = josephson_energy_ghz_from_ic(0.02)
    lj = josephson_energy_ghz_from_lj(2.067833848e-15 / (2 * math.pi * 20e-9) * 1e9)
    assert ic == pytest.approx(lj, rel=1e-9)
    assert ic == pytest.approx(9.9337, rel=1e-3)
    with pytest.raises(ValueError, match="exactly one"):
        JunctionModel(name="x", josephson_energy_ghz=1.0, critical_current_ua=1.0)


def test_epr_reproduces_transmon_limit() -> None:
    analysis = _transmon()
    # alpha = chi_11 / 2 = -E_C ;  f01 = f_lin + chi_11/2 + chi_12/2 ~ sqrt(8 EJ EC) - EC
    assert analysis.anharmonicity_ghz["1"] == pytest.approx(-EC, rel=1e-9)
    assert analysis.chi_matrix_ghz["1"]["1"] == pytest.approx(-2 * EC, rel=1e-9)
    assert analysis.dressed_frequency_ghz["1"] == pytest.approx(
        F_LIN - EC + analysis.chi_matrix_ghz["1"]["2"] / 2, rel=1e-9
    )
    assert analysis.chi_matrix_ghz["1"]["2"] == analysis.chi_matrix_ghz["2"]["1"]
    assert analysis.chi_matrix_ghz["1"]["2"] < 0
    assert analysis.qubit_mode_index == 1
    assert analysis.status is EvidenceStatus.ANALYTICAL_ONLY
    assert analysis.zpf_matrix_rad["1"]["J1"] == pytest.approx(math.sqrt(F_LIN / (2 * EJ)))


def test_epr_warns_when_nothing_participates() -> None:
    analysis = epr_from_participations(
        [ModeEnergy(index=1, frequency_ghz=5.0)],
        [JunctionModel(name="J1", josephson_energy_ghz=EJ)],
        cross_check=False,
    )
    assert analysis.qubit_mode_index is None
    assert any("no qubit identified" in w for w in analysis.warnings)
    with pytest.raises(ValueError, match="sum above one"):
        ModeEnergy(index=1, frequency_ghz=5.0, junction_participation={"a": 0.7, "b": 0.6})


@pytest.mark.skipif(
    not scqubits_available(), reason="scqubits not installed (install the `quantum` extra)"
)
def test_scqubits_cross_check_agrees_with_epr_within_first_order() -> None:
    analysis = _transmon(cross_check=True)
    check = analysis.scqubits_cross_check
    assert check is not None and check.status is EvidenceStatus.SIMULATION_EXECUTED
    assert check.f01_deviation_percent is not None and check.f01_deviation_percent < 0.5
    # First-order EPR underestimates |alpha| at E_J/E_C = 80 by ~10 %; that is reported, not hidden.
    assert (
        check.anharmonicity_deviation_percent is not None
        and 5.0 < check.anharmonicity_deviation_percent < 15.0
    )


def test_scqubits_cross_check_absent_is_skipped_not_fabricated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("textlayout.quantum.epr.scqubits_available", lambda: False)
    check = scqubits_transmon_cross_check(
        e_j_ghz=EJ, e_c_ghz=EC, epr_f01_ghz=6.0, epr_anharmonicity_ghz=-0.25
    )
    assert check.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT
    assert check.f01_ghz is None
    analysis = _transmon(cross_check=True)
    assert analysis.scqubits_cross_check is not None
    assert analysis.scqubits_cross_check.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT


def _palace_postpro(tmp_path: Path, *, with_ports: bool) -> Path:
    postpro = tmp_path / "postpro"
    postpro.mkdir()
    (postpro / "eig.csv").write_text(
        "m,Re{f} (GHz),Im{f} (GHz),Q,Error (Bkwd.),Error (Abs.)\n"
        f"1,{F_LIN},1e-6,1e6,0,0\n2,7.2,1e-6,2e6,0,0\n",
        encoding="utf-8",
    )
    (postpro / "domain-E.csv").write_text(
        "m,E_elec (J),E_mag (J),E_cap (J),E_ind (J),E_elec[1] (J),p_elec[1],E_mag[1] (J),p_mag[1],E_elec[2] (J),p_elec[2],E_mag[2] (J),p_mag[2]\n"
        "1,1e-12,2e-13,0,8e-13,9e-13,0.9,1.5e-13,0.75,1e-13,0.1,5e-14,0.25\n"
        "2,1e-12,1e-12,0,1e-14,5e-13,0.5,5e-13,0.5,5e-13,0.5,5e-13,0.5\n",
        encoding="utf-8",
    )
    if with_ports:
        (postpro / "port-EPR.csv").write_text("m,p[1]\n1,0.8\n2,0.01\n", encoding="utf-8")
    return postpro


def test_modes_from_palace_output_reads_energy_distribution_and_participation(
    tmp_path: Path,
) -> None:
    postpro = _palace_postpro(tmp_path, with_ports=True)
    junction = JunctionModel(name="J1", josephson_energy_ghz=EJ, port_index=1)
    modes = modes_from_palace_output(
        postpro, [junction], region_names={1: "substrate", 2: "vacuum"}
    )
    assert [m.index for m in modes] == [1, 2]
    assert modes[0].junction_participation == {"J1": 0.8}
    assert modes[0].electric_energy_fraction == {"substrate": 0.9, "vacuum": 0.1}
    assert modes[0].magnetic_energy_fraction == {"substrate": 0.75, "vacuum": 0.25}
    assert modes[0].kinetic_energy_fraction == pytest.approx(0.8)
    assert modes[0].quality_factor == pytest.approx(1e6)
    analysis = analyze_palace_output(
        postpro, [junction], region_names={1: "substrate", 2: "vacuum"}, cross_check=False
    )
    assert (
        analysis.status is EvidenceStatus.SIMULATION_EXECUTED and analysis.source == "palace_fields"
    )
    assert analysis.qubit_mode_index == 1
    assert analysis.anharmonicity_ghz["1"] == pytest.approx(-(F_LIN**2) * 0.8**2 / (8 * EJ))
    assert analysis.dielectric_participation["1"]["substrate"] == 0.9


def test_palace_output_without_ports_is_simulation_invalid_and_missing_is_skipped(
    tmp_path: Path,
) -> None:
    postpro = _palace_postpro(tmp_path, with_ports=False)
    junction = JunctionModel(name="J1", josephson_energy_ghz=EJ, port_index=1)
    invalid = analyze_palace_output(postpro, [junction])
    assert invalid.status is EvidenceStatus.SIMULATION_INVALID
    assert invalid.qubit_mode_index is None and invalid.chi_matrix_ghz == {}
    assert invalid.dielectric_participation["1"]["domain_1"] == 0.9
    skipped = analyze_palace_output(tmp_path / "nowhere", [junction])
    assert skipped.status is EvidenceStatus.SKIPPED_SOLVER_ABSENT
    assert skipped.source == "none" and skipped.modes == []


def test_quantum_analysis_persists_and_embeds_idempotently(tmp_path: Path) -> None:
    analysis = _transmon()
    path = write_quantum_analysis(analysis, tmp_path)
    assert path.name == "quantum_analysis.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "textlayout.quantum-analysis.v1"
    assert payload["status"] == "ANALYTICAL_ONLY"
    assert payload["anharmonicity_ghz"]["1"] == pytest.approx(-EC)
    assert set(payload["chi_matrix_ghz"]["1"]) == {"1", "2"}

    report = tmp_path / "report.md"
    report.write_text("# Report\n\nGeometry section.\n", encoding="utf-8")
    embed_in_report(report, analysis)
    embed_in_report(report, analysis)
    text = report.read_text(encoding="utf-8")
    assert text.count(REPORT_BEGIN) == 1 and text.count(REPORT_END) == 1
    assert text.startswith("# Report\n\nGeometry section.\n")
    assert "## Quantum (EPR) analysis" in text
    assert "Cross-Kerr chi (GHz)" in text
    summary = render_quantum_summary(analysis)
    assert "`ANALYTICAL_ONLY`" in summary and "| 1 | 6.3246 |" in summary
