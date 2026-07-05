"""End-to-end regression guard for examples/real_cqed_loop.py.

This is the CI-facing proof that the seven cQED design-loop upgrades
(EPR/coherence, JJ yield, chip collisions, PDK, measurement correlation)
compose into one working pipeline, not just seven isolated unit-tested
modules. It must run with zero external/commercial solvers.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = REPO_ROOT / "examples" / "real_cqed_loop.py"


def _load_demo_module():
    spec = importlib.util.spec_from_file_location("real_cqed_loop_demo", DEMO_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_demo_runs_and_produces_all_seven_steps(tmp_path, monkeypatch, capsys) -> None:
    module = _load_demo_module()
    # PDK_PATH / MEASUREMENT_FIXTURES were already resolved against the real
    # REPO_ROOT at module-load time, so this only redirects main()'s evidence
    # *output* directory away from the real repo's out/evidence/.
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)

    report = module.main()
    capsys.readouterr()
    assert (tmp_path / "out" / "evidence" / "real_cqed_loop_report.json").is_file()
    assert (tmp_path / "out" / "evidence" / "real_cqed_loop_report.md").is_file()

    step_names = [s["step"] for s in report["steps"]]
    assert step_names == [
        "1_load_pdk",
        "2_generate_geometry",
        "3_4_epr_and_coherence",
        "5_jj_yield",
        "6_chip_collisions",
        "7_measurement_correlation",
    ]


def test_demo_pdk_step_is_not_foundry_validated() -> None:
    module = _load_demo_module()
    step1, pdk = module.step_1_load_pdk()
    assert step1["pdk"]["foundry_validated"] is False


def test_demo_geometry_step_passes_verification() -> None:
    module = _load_demo_module()
    _, pdk = module.step_1_load_pdk()
    step2, spec, capacitance = module.step_2_generate_geometry(pdk)
    assert step2["status"] == "GEOMETRY_PASS"
    assert capacitance > 0


def test_demo_jj_yield_targets_the_design_frequency() -> None:
    """Regression guard for the junction-area solving bug fixed during development:
    an earlier version sized the junction from the PDK's minimum-area floor
    directly, which resonated at ~1 GHz against a 5 GHz target (0% yield, a
    systematic miss, not a meaningful spread result)."""
    module = _load_demo_module()
    _, pdk = module.step_1_load_pdk()
    _, _, capacitance = module.step_2_generate_geometry(pdk)
    step5, jj_result = module.step_5_jj_yield(pdk, capacitance)
    assert abs(step5["mean_frequency_ghz"] - module.DESIGN_TARGET_FREQUENCY_GHZ) < 0.1
    assert step5["yield_pct"] > 5.0  # a correctly-centered design should not be near 0%


def test_demo_chip_collisions_uses_realistic_sigma() -> None:
    module = _load_demo_module()
    step6 = module.step_6_chip_collisions(freq_sigma_mhz=50.0)
    assert step6["n_nodes"] == 4
    assert 0.0 <= step6["collision_free_pct"] <= 100.0


def test_demo_measurement_step_uses_committed_fixtures() -> None:
    module = _load_demo_module()
    step7 = module.step_7_measurement_correlation(estimated_capacitance_pf=0.6)
    assert step7["n_records"] == 3
    assert step7["status"] == "SYNTHETIC"


def test_demo_report_has_no_unlabeled_claims(tmp_path, monkeypatch) -> None:
    """Every step must carry a status field from the documented legend, and no
    step may itself claim PHYSICS_VERIFIED (the honesty summary explicitly
    disclaims it in prose, which is different from a step status field)."""
    module = _load_demo_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    report = module.main()
    legend = set(report["status_legend"])
    for step in report["steps"]:
        assert step["status"] in legend, f"{step['step']} has an undocumented status"
        assert step["status"] != "PHYSICS_VERIFIED"
    assert "Nothing in this report is PHYSICS_VERIFIED" in report["honesty_summary"][0]
