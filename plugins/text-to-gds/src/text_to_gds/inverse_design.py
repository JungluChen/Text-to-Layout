"""Differentiable EM interfaces, trainable GDS parameters, adjoints, and spectral surrogates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
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
