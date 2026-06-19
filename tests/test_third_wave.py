from __future__ import annotations

import math

import numpy as np
import pytest
from PIL import Image

from text_to_gds.inverse_design import (
    DifferentiableEMSolver,
    DifferentiableGDSPipeline,
    TrainableGDSParameter,
    linear_adjoint_gradient,
    predict_neural_operator,
    train_neural_operator,
)
from text_to_gds.scientist_extensions import (
    align_microscope_to_gds,
    check_amplifier_claim,
    discover_equation,
    full_cryostat_twin,
    reproduction_score,
    tapeout_checklist,
    understand_sem_image,
)
from text_to_gds.third_wave import (
    call_third_wave_improvement,
    list_third_wave_improvements,
    validate_third_wave_registry,
)


def test_third_wave_registry_covers_37_new_and_340_total_capabilities():
    registry = list_third_wave_improvements()
    assert registry["count"] == 37
    assert registry["total_platform_capabilities"] == 340
    assert [feature["id"] for feature in registry["features"]] == list(range(1, 38))
    assert validate_third_wave_registry() == {
        "passed": True,
        "count": 37,
        "missing": [],
        "unresolved": [],
    }
    assert call_third_wave_improvement(10, electrical_length_rad=0.05, coupling_strength_fraction=0.01, geometry_3d=False, required_relative_error=0.05)["selected_model"] == "lumped_lc"


def test_differentiable_em_and_trainable_gds_pipeline():
    solver = DifferentiableEMSolver(lambda p: {"frequency": 10.0 - p["length"], "bandwidth": 2.0 * p["gap"]})
    jacobian = solver.jacobian({"length": 4.0, "gap": 0.5}, ["frequency", "bandwidth"])
    assert jacobian["frequency"]["length"] == pytest.approx(-1.0)
    assert jacobian["bandwidth"]["gap"] == pytest.approx(2.0)
    pipeline = DifferentiableGDSPipeline([TrainableGDSParameter("length", 4.0, 1.0, 9.0), TrainableGDSParameter("gap", 0.5, 0.1, 2.0)], solver)
    result = pipeline.optimize({"frequency": 6.0, "bandwidth": 2.0}, iterations=20, learning_rate=0.1)
    assert result["prediction"]["frequency"] == pytest.approx(6.0, abs=1e-8)
    assert result["prediction"]["bandwidth"] == pytest.approx(2.0, abs=1e-8)


def test_linear_adjoint_matches_analytic_gradient():
    result = linear_adjoint_gradient(
        {"p": 2.0},
        matrix_builder=lambda parameters: np.asarray([[parameters["p"]]], dtype=float),
        rhs_builder=lambda parameters: np.asarray([1.0]),
        observation_matrix=np.asarray([[1.0]]),
        target=np.asarray([0.0]),
    )
    assert result["loss"] == pytest.approx(0.125)
    assert result["gradient"]["p"] == pytest.approx(-0.125, rel=1e-5)
    assert result["method"] == "discrete_linear_adjoint"


def test_fourier_neural_operator_and_equation_discovery():
    x = np.linspace(0.0, 1.0, 32)
    geometry = [np.sin(2.0 * math.pi * x * scale).tolist() for scale in (1, 2, 3, 4, 5, 6)]
    responses = [[float(np.mean(np.asarray(profile) ** 2)), float(np.max(profile))] for profile in geometry]
    model = train_neural_operator(geometry, responses, retained_modes=8)
    prediction = predict_neural_operator(model, geometry[2])
    assert prediction == pytest.approx(responses[2], abs=1e-5)

    variables = {"x": np.linspace(-2, 2, 41).tolist()}
    target = (3.0 + 2.0 * np.asarray(variables["x"]) + 0.5 * np.asarray(variables["x"]) ** 2).tolist()
    equation = discover_equation(variables, target)
    assert equation["r_squared"] > 0.999999
    assert "x^2" in equation["terms"]


def test_cryostat_twin_sem_understanding_and_alignment(tmp_path):
    stages = [{"temperature_k": value} for value in (300.0, 50.0, 4.0, 0.8, 0.1, 0.01)]
    twin = full_cryostat_twin(stages, [{"name": "attenuator", "loss_db": 20.0, "temperature_k": 4.0}])
    assert twin["complete"] is True
    image = np.zeros((64, 64), dtype=np.uint8)
    image[20:40, 24:44] = 255
    image_path = tmp_path / "sem.png"
    Image.fromarray(image).save(image_path)
    result = understand_sem_image(image_path, pixel_size_nm=10.0, threshold=128)
    assert result["actual_area_um2"] == pytest.approx(0.04)
    shifted = np.roll(image, (3, -4), axis=(0, 1))
    alignment = align_microscope_to_gds(image, shifted, pixel_size_nm=10.0)
    assert alignment["shift_pixels_yx"] == [-3, 4]


def test_claim_tapeout_and_reproduction_gates():
    claim = check_amplifier_claim(gain_db=20.0, bandwidth_hz=500e6, center_frequency_hz=6e9, added_noise_photons=0.5)
    assert claim["plausible"] is True
    tapeout = tapeout_checklist({"gds_hash": "abc", "process": "ncu@1.0.0", "drc_passed": True, "lvs_passed": True, "em_converged": True, "dfm_passed": True, "waivers_reviewed": True, "mask_reviewed": True, "provenance_archived": True})
    assert tapeout["ready"] is True
    score = reproduction_score({"gain": {"reported": 20.0, "reproduced": 19.0}, "bandwidth": {"reported": 500.0, "reproduced": 450.0}})
    assert score["overall_score"] == pytest.approx(0.925)
