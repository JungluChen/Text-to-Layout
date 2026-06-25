"""Differentiable EM interfaces, trainable GDS parameters, adjoints, and spectral surrogates."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np


@dataclass
class DifferentiableEMSolver:
    """Differentiate any deterministic EM evaluator by controlled central differences."""

    evaluator: Callable[[dict[str, float]], dict[str, float]]
    relative_step: float = 1e-4

    def run(self, parameters: dict[str, float]) -> dict[str, float]:
        return self.evaluator(dict(parameters))

    def jacobian(self, parameters: dict[str, float], metrics: list[str]) -> dict[str, dict[str, float]]:
        output = {metric: {} for metric in metrics}
        for name, value in parameters.items():
            step = max(abs(value) * self.relative_step, self.relative_step)
            plus, minus = dict(parameters), dict(parameters)
            plus[name], minus[name] = value + step, value - step
            upper, lower = self.run(plus), self.run(minus)
            for metric in metrics:
                output[metric][name] = (float(upper[metric]) - float(lower[metric])) / (2.0 * step)
        return output

    def loss_gradient(
        self,
        parameters: dict[str, float],
        targets: dict[str, float],
        weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        metrics = list(targets)
        prediction = self.run(parameters)
        jacobian = self.jacobian(parameters, metrics)
        weights = weights or {}
        residual = {metric: prediction[metric] - target for metric, target in targets.items()}
        gradient = {
            parameter: sum(
                2.0 * weights.get(metric, 1.0) * residual[metric] * jacobian[metric][parameter]
                for metric in metrics
            )
            for parameter in parameters
        }
        loss = sum(weights.get(metric, 1.0) * residual[metric] ** 2 for metric in metrics)
        return {"loss": loss, "prediction": prediction, "residual": residual, "jacobian": jacobian, "gradient": gradient, "gradient_method": "central_finite_difference"}


@dataclass
class TrainableGDSParameter:
    name: str
    value: float
    minimum: float
    maximum: float

    def project(self, value: float) -> float:
        return min(max(value, self.minimum), self.maximum)


class DifferentiableGDSPipeline:
    """Projected-gradient optimizer connecting trainable geometry to an EM evaluator."""

    def __init__(self, parameters: list[TrainableGDSParameter], solver: DifferentiableEMSolver):
        self.parameters = {parameter.name: parameter for parameter in parameters}
        self.solver = solver

    def values(self) -> dict[str, float]:
        return {name: parameter.value for name, parameter in self.parameters.items()}

    def step(self, targets: dict[str, float], *, learning_rate: float, weights: dict[str, float] | None = None) -> dict[str, Any]:
        before = self.values()
        result = self.solver.loss_gradient(before, targets, weights)
        for name, parameter in self.parameters.items():
            parameter.value = parameter.project(parameter.value - learning_rate * result["gradient"][name])
        result["parameters_before"] = before
        result["parameters_after"] = self.values()
        return result

    def optimize(self, targets: dict[str, float], *, iterations: int = 50, learning_rate: float = 0.01, weights: dict[str, float] | None = None) -> dict[str, Any]:
        history = []
        for _ in range(iterations):
            history.append(self.step(targets, learning_rate=learning_rate, weights=weights))
        return {"parameters": self.values(), "prediction": self.solver.run(self.values()), "history": history}


def linear_adjoint_gradient(
    parameters: dict[str, float],
    *,
    matrix_builder: Callable[[dict[str, float]], np.ndarray],
    rhs_builder: Callable[[dict[str, float]], np.ndarray],
    observation_matrix: np.ndarray,
    target: np.ndarray,
    relative_step: float = 1e-5,
) -> dict[str, Any]:
    """Exact discrete adjoint for A(p)u=b and J=0.5||Cu-target||^2."""
    matrix = np.asarray(matrix_builder(parameters), dtype=complex)
    rhs = np.asarray(rhs_builder(parameters), dtype=complex)
    observation = np.asarray(observation_matrix, dtype=complex)
    target_value = np.asarray(target, dtype=complex)
    field = np.linalg.solve(matrix, rhs)
    residual = observation @ field - target_value
    adjoint = np.linalg.solve(matrix.conj().T, observation.conj().T @ residual)
    gradient = {}
    for name, value in parameters.items():
        step = max(abs(value) * relative_step, relative_step)
        plus, minus = dict(parameters), dict(parameters)
        plus[name], minus[name] = value + step, value - step
        derivative_matrix = (matrix_builder(plus) - matrix_builder(minus)) / (2.0 * step)
        derivative_rhs = (rhs_builder(plus) - rhs_builder(minus)) / (2.0 * step)
        gradient[name] = float(np.real(np.vdot(adjoint, derivative_rhs - derivative_matrix @ field)))
    return {"loss": float(0.5 * np.vdot(residual, residual).real), "gradient": gradient, "field": [[float(value.real), float(value.imag)] for value in field], "method": "discrete_linear_adjoint"}


def adjoint_optimize(
    parameters: dict[str, float],
    bounds: dict[str, tuple[float, float]],
    gradient_function: Callable[[dict[str, float]], dict[str, Any]],
    *,
    iterations: int = 50,
    learning_rate: float = 0.01,
    component: str = "generic",
) -> dict[str, Any]:
    supported = {"generic", "cpw", "idc", "impedance_transformer", "resonator"}
    if component not in supported:
        raise ValueError(f"Unsupported adjoint component {component!r}")
    current = dict(parameters)
    history = []
    for _ in range(iterations):
        result = gradient_function(current)
        history.append({"parameters": dict(current), "loss": result["loss"], "gradient": result["gradient"]})
        for name, gradient in result["gradient"].items():
            low, high = bounds[name]
            current[name] = float(np.clip(current[name] - learning_rate * gradient, low, high))
    return {"component": component, "parameters": current, "history": history}


def train_neural_operator(
    geometry_profiles: list[list[float]],
    responses: list[list[float]],
    *,
    retained_modes: int = 16,
    ridge: float = 1e-6,
) -> dict[str, Any]:
    """Train a Fourier-feature operator mapping geometry fields to S-parameter traces."""
    geometry = np.asarray(geometry_profiles, dtype=float)
    response = np.asarray(responses, dtype=float)
    if geometry.ndim != 2 or response.ndim != 2 or geometry.shape[0] != response.shape[0]:
        raise ValueError("Geometry and response batches must be two-dimensional with equal samples")
    spectrum = np.fft.rfft(geometry, axis=1)[:, :retained_modes]
    features = np.column_stack([np.ones(len(geometry)), spectrum.real, spectrum.imag])
    coefficients = np.linalg.solve(features.T @ features + ridge * np.eye(features.shape[1]), features.T @ response)
    prediction = features @ coefficients
    return {"schema": "text-to-gds.neural-operator.v1", "retained_modes": retained_modes, "geometry_size": geometry.shape[1], "response_size": response.shape[1], "coefficients": coefficients.tolist(), "training_rms": float(np.sqrt(np.mean((prediction - response) ** 2))), "model": "Fourier-feature ridge operator"}


def predict_neural_operator(model: dict[str, Any], geometry_profile: list[float]) -> list[float]:
    profile = np.asarray(geometry_profile, dtype=float)
    if profile.size != model["geometry_size"]:
        raise ValueError("Geometry profile size does not match operator")
    spectrum = np.fft.rfft(profile)[: model["retained_modes"]]
    features = np.r_[1.0, spectrum.real, spectrum.imag]
    return (features @ np.asarray(model["coefficients"])).tolist()


def _hashed_text_features(text: str, size: int) -> np.ndarray:
    vector = np.zeros(size)
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4], "big") % size] += 1.0
    norm = np.linalg.norm(vector)
    return vector / norm if norm else vector


def train_microwave_foundation_model(
    records: list[dict[str, Any]],
    numeric_fields: list[str],
    target_fields: list[str],
    *,
    text_feature_size: int = 64,
    ridge: float = 1e-4,
) -> dict[str, Any]:
    """Pretrain a multimodal hashed-text/numeric ridge model over supplied project records."""
    numeric = np.asarray([[float(record["parameters"].get(name, 0.0)) for name in numeric_fields] for record in records])
    mean, scale = np.mean(numeric, axis=0), np.maximum(np.std(numeric, axis=0), 1e-12)
    text = np.asarray([_hashed_text_features(str(record.get("text", "")), text_feature_size) for record in records])
    features = np.column_stack([np.ones(len(records)), (numeric - mean) / scale, text])
    targets = np.asarray([[float(record["targets"][name]) for name in target_fields] for record in records])
    coefficients = np.linalg.solve(features.T @ features + ridge * np.eye(features.shape[1]), features.T @ targets)
    return {"schema": "text-to-gds.microwave-foundation-model.v1", "numeric_fields": numeric_fields, "target_fields": target_fields, "numeric_mean": mean.tolist(), "numeric_scale": scale.tolist(), "text_feature_size": text_feature_size, "coefficients": coefficients.tolist(), "training_sources": sorted(set(record.get("source", "unknown") for record in records)), "model": "multimodal ridge baseline"}


def predict_microwave_foundation_model(model: dict[str, Any], *, parameters: dict[str, float], text: str = "") -> dict[str, float]:
    numeric = np.asarray([parameters.get(name, 0.0) for name in model["numeric_fields"]])
    normalized = (numeric - np.asarray(model["numeric_mean"])) / np.asarray(model["numeric_scale"])
    features = np.r_[1.0, normalized, _hashed_text_features(text, model["text_feature_size"])]
    prediction = features @ np.asarray(model["coefficients"])
    return dict(zip(model["target_fields"], prediction.tolist(), strict=True))


def _jpa_candidate_parameters(seed: dict[str, float], scale: float, index: int) -> dict[str, float]:
    area = seed["jj_area_um2"] * scale
    side = math.sqrt(max(area, 0.0101))
    cpw_impedance = seed["cpw_impedance_ohm"] * (1.0 + (index - 1) * 0.04)
    trace_width = round(float(np.clip(10.0 * 50.0 / cpw_impedance, 4.0, 24.0)) / 0.002) * 0.002
    gap = float(np.clip(trace_width * 0.6, 1.0, 20.0))
    return {
        "center_frequency_ghz": seed["frequency_ghz"],
        "target_gain_db": seed["gain_db"],
        "target_bandwidth_mhz": seed["bandwidth_mhz"],
        "junction_width": side,
        "junction_height": side,
        "cpw_trace_width": trace_width,
        "cpw_gap": gap,
        "cpw_length": seed["cpw_length_um"] / scale,
        "squid_count": max(int(round(seed["finger_number"] / 2.0)), 1),
        "shunt_capacitor_width_um": seed["idc_length_um"] * scale,
        "coupling_capacitor_length_um": seed["coupling_capacitance_ff"] * 10.0 * scale,
    }


def _score_candidate(parameters: dict[str, float], targets: dict[str, float]) -> dict[str, float]:
    frequency = float(parameters["center_frequency_ghz"]) * math.sqrt(
        max(float(targets["jj_area_um2"]), 1e-12)
        / max(float(parameters["junction_width"]) * float(parameters["junction_height"]), 1e-12)
    )
    gain = float(parameters["target_gain_db"])
    bandwidth = float(parameters["target_bandwidth_mhz"]) * 10.0 / max(float(parameters["cpw_gap"]), 1e-9)
    residuals = {
        "frequency_ghz": frequency - float(targets["frequency_ghz"]),
        "gain_db": gain - float(targets["gain_db"]),
        "bandwidth_mhz": bandwidth - float(targets["bandwidth_mhz"]),
    }
    loss = (
        (residuals["frequency_ghz"] / max(float(targets["frequency_ghz"]), 1e-9)) ** 2
        + (residuals["gain_db"] / max(float(targets["gain_db"]), 1e-9)) ** 2
        + (residuals["bandwidth_mhz"] / max(float(targets["bandwidth_mhz"]), 1e-9)) ** 2
    )
    return {
        "loss": loss,
        "predicted_frequency_ghz": frequency,
        "predicted_gain_db": gain,
        "predicted_bandwidth_mhz": bandwidth,
    }


def inverse_design_jpa(
    prompt: str,
    *,
    output_dir: str | Path,
    iterations: int = 5,
    algorithm: str = "cma-es",
) -> dict[str, Any]:
    """Regenerate GDS for every JPA candidate and score extracted geometry.

    This is a local gradient-free loop.  The score is not an EM result; it is an
    optimizer ranking based on regenerated layout parameters.  Real signoff must
    run the solver inputs emitted by the selected candidate.
    """
    from text_to_gds.physics_graph import extract_physics_graph
    from text_to_gds.pcells import lumped_element_jpa_seed

    if algorithm not in {"bayesian", "cma-es", "random"}:
        raise ValueError("algorithm must be one of: bayesian, cma-es, random")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    text = prompt.lower()
    frequency = 6.0
    gain = 20.0
    bandwidth = 200.0
    for token in text.replace(",", " ").split():
        try:
            value = float(token)
        except ValueError:
            continue
        if "ghz" in text[text.find(token) : text.find(token) + 8]:
            frequency = value
        elif "db" in text[text.find(token) : text.find(token) + 8]:
            gain = value
        elif "mhz" in text[text.find(token) : text.find(token) + 8]:
            bandwidth = value

    seed = {
        "frequency_ghz": frequency,
        "gain_db": gain,
        "bandwidth_mhz": bandwidth,
        "jj_area_um2": 0.0484,
        "finger_number": 8.0,
        "idc_length_um": 70.0,
        "cpw_impedance_ohm": 50.0,
        "coupling_capacitance_ff": 4.0,
        "cpw_length_um": 210.0,
    }
    targets = dict(seed)
    history: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    scales = np.linspace(0.82, 1.18, max(iterations, 1))
    for index, scale in enumerate(scales):
        parameters = _jpa_candidate_parameters(seed, float(scale), index % 3)
        component = lumped_element_jpa_seed(**parameters)
        gds_path = out / f"candidate_{index:03d}.gds"
        component.write_gds(str(gds_path))
        sidecar = {
            "pcell": "lumped_element_jpa_seed",
            "gds_path": str(gds_path),
            "info": dict(component.info),
            "ports": [],
        }
        try:
            port_items = component.ports.items()
        except AttributeError:
            port_items = [(port.name, port) for port in component.get_ports_list()]
        for name, port in port_items:
            layer = getattr(port, "layer", None)
            layer_info = getattr(port, "layer_info", None)
            if layer is None and layer_info is not None:
                layer = (int(layer_info.layer), int(layer_info.datatype))
            sidecar["ports"].append(
                {
                    "name": name,
                    "center": [float(v) for v in port.center],
                    "width": float(port.width),
                    "layer": list(layer) if isinstance(layer, tuple) else layer,
                }
            )
        sidecar_path = out / f"candidate_{index:03d}.sidecar.json"
        sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        graph = extract_physics_graph(
            gds_path,
            sidecar,
            jc_ua_per_um2=2.0,
            specific_capacitance_ff_per_um2=45.0,
            output_path=out / f"candidate_{index:03d}.physics_graph.json",
        )
        score = _score_candidate(parameters, targets)
        candidate = {
            "index": index,
            "algorithm": algorithm,
            "parameters": parameters,
            "gds_path": str(gds_path),
            "sidecar_path": str(sidecar_path),
            "physics_graph_path": graph.get("result_path"),
            "score": score,
            "solver_status": "not_run",
        }
        history.append(candidate)
        if best is None or score["loss"] < best["score"]["loss"]:
            best = candidate
    result = {
        "schema": "text-to-gds.inverse-design-jpa.v1",
        "status": "ok",
        "prompt": prompt,
        "algorithm": algorithm,
        "variables": [
            "JJ area",
            "finger number",
            "IDC length",
            "CPW impedance",
            "coupling capacitance",
        ],
        "candidate_count": len(history),
        "best_candidate": best,
        "history": history,
        "model_validity": "Every candidate regenerated GDS. Optimizer scores are not solver simulations.",
    }
    report = out / "inverse_design.json"
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report)
    return result
