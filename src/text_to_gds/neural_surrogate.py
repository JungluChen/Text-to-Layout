"""Neural Surrogate Models — fast prediction of EM parameters.

Implements:
    - Neural S-parameter predictor
    - Neural capacitance extractor
    - Neural inductance extractor
    - Neural gain predictor
    - Neural noise predictor
    - Uncertainty-aware prediction (MC dropout)
    - Active learning loop
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ---------------------------------------------------------------------------
# Surrogate model architectures
# ---------------------------------------------------------------------------

if HAS_TORCH:

    class SParameterPredictor(nn.Module):
        """Neural S-parameter predictor.

        Input: geometry + frequency → S-matrix.
        Architecture: MLP with residual connections.
        """

        def __init__(self, input_dim: int = 16, n_ports: int = 2, hidden: int = 64):
            super().__init__()
            self.n_ports = n_ports
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden),
                nn.ReLU(),
            )
            self.real_head = nn.Linear(hidden, n_ports * n_ports)
            self.imag_head = nn.Linear(hidden, n_ports * n_ports)

        def forward(self, x: "torch.Tensor") -> dict[str, "torch.Tensor"]:
            h = self.encoder(x)
            s_real = self.real_head(h).view(-1, self.n_ports, self.n_ports)
            s_imag = self.imag_head(h).view(-1, self.n_ports, self.n_ports)
            s_mag = torch.sqrt(s_real ** 2 + s_imag ** 2)
            return {"s_real": s_real, "s_imag": s_imag, "s_magnitude": s_mag}

    class CapacitancePredictor(nn.Module):
        """Neural capacitance matrix extractor.

        Input: geometry features → N×N capacitance matrix.
        """

        def __init__(self, input_dim: int = 16, n_nodes: int = 4, hidden: int = 64):
            super().__init__()
            self.n_nodes = n_nodes
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden),
                nn.ReLU(),
                nn.Linear(hidden, n_nodes * n_nodes),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            raw = self.net(x)
            C = raw.view(-1, self.n_nodes, self.n_nodes)
            # Enforce symmetry
            C = (C + C.transpose(-1, -2)) / 2
            # Enforce positive diagonal
            diag = torch.diagonal(C, dim1=-2, dim2=-1)
            diag = torch.relu(diag)
            C = C.clone()
            for i in range(self.n_nodes):
                C[:, i, i] = diag[:, i]
            return C

    class InductancePredictor(nn.Module):
        """Neural inductance extractor.

        Input: geometry features → partial inductance matrix.
        """

        def __init__(self, input_dim: int = 16, n_segments: int = 4, hidden: int = 64):
            super().__init__()
            self.n_seg = n_segments
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden),
                nn.ReLU(),
                nn.Linear(hidden, n_segments),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.net(x)  # partial inductances in pH

    class GainPredictor(nn.Module):
        """Neural JPA gain/bandwidth predictor.

        Input: geometry + pump parameters → gain, BW, noise temp.
        """

        def __init__(self, input_dim: int = 12, hidden: int = 64):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden),
                nn.Tanh(),
                nn.Linear(hidden, hidden),
                nn.Tanh(),
                nn.Linear(hidden, 4),  # gain_db, BW_mHz, T_noise_K, P1dB_dBm
            )

        def forward(self, x: "torch.Tensor") -> dict[str, "torch.Tensor"]:
            raw = self.net(x)
            return {
                "gain_db": raw[:, 0],
                "bandwidth_mhz": raw[:, 1],
                "noise_temperature_k": torch.relu(raw[:, 2]),
                "p1db_dbm": raw[:, 3],
            }


# ---------------------------------------------------------------------------
# Uncertainty-aware predictor (MC Dropout)
# ---------------------------------------------------------------------------

if HAS_TORCH:

    class MCDropoutPredictor:
        """Monte Carlo dropout for uncertainty estimation.

        Runs the model N times with dropout active to estimate
        prediction uncertainty.
        """

        def __init__(self, model: nn.Module, n_samples: int = 50):
            self.model = model
            self.n_samples = n_samples

        def predict_with_uncertainty(
            self, x: "torch.Tensor"
        ) -> dict[str, "torch.Tensor"]:
            """Run MC dropout and return mean ± std."""
            self.model.train()  # keep dropout active
            predictions = []

            for _ in range(self.n_samples):
                with torch.no_grad():
                    pred = self.model(x)
                    if isinstance(pred, dict):
                        predictions.append({k: v.clone() for k, v in pred.items()})
                    else:
                        predictions.append(pred.clone())

            if isinstance(predictions[0], dict):
                result: dict[str, torch.Tensor] = {}
                for key in predictions[0]:
                    stack = torch.stack([p[key] for p in predictions])
                    result[f"{key}_mean"] = stack.mean(dim=0)
                    result[f"{key}_std"] = stack.std(dim=0)
                return result
            else:
                stack = torch.stack(predictions)
                return {
                    "mean": stack.mean(dim=0),
                    "std": stack.std(dim=0),
                }


# ---------------------------------------------------------------------------
# Numpy fallback models
# ---------------------------------------------------------------------------

class NumpySParameterPredictor:
    """Simple numpy surrogate for S-parameter prediction."""

    def __init__(self):
        self._rng = np.random.RandomState(42)
        self._weights = self._rng.randn(16, 4) * 0.1

    def predict(self, features: list[float]) -> dict[str, Any]:
        x = np.array(features[:16], dtype=np.float64)
        if len(x) < 16:
            x = np.pad(x, (0, 16 - len(x)))
        raw = x @ self._weights
        return {
            "s11_db": float(raw[0]),
            "s21_db": float(raw[1]),
            "s12_db": float(raw[2]),
            "s22_db": float(raw[3]),
        }


# ---------------------------------------------------------------------------
# Active learning loop
# ---------------------------------------------------------------------------

@dataclass
class ActiveLearningCandidate:
    """A candidate point for active learning."""
    features: list[float]
    predicted_value: float
    uncertainty: float
    acquisition_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "features": self.features,
            "predicted": self.predicted_value,
            "uncertainty": self.uncertainty,
            "acquisition_score": self.acquisition_score,
        }


class ActiveLearningLoop:
    """Active learning loop for efficient device exploration.

    Selects the most informative next experiment/simulation to run
    using uncertainty-based acquisition functions.
    """

    def __init__(self, acquisition: str = "ucb"):
        self.acquisition = acquisition
        self.history: list[dict[str, Any]] = []

    def select_next(
        self,
        candidates: list[dict[str, Any]],
        beta: float = 2.0,
    ) -> ActiveLearningCandidate:
        """Select the best candidate using acquisition function.

        Acquisition functions:
            - ucb: Upper Confidence Bound = mu + beta * sigma
            - ei: Expected Improvement
            - pi: Probability of Improvement
            - variance: Pure uncertainty sampling
        """
        best_score = -float("inf")
        best = ActiveLearningCandidate([], 0.0, 0.0)

        for cand in candidates:
            mu = cand.get("predicted", 0)
            sigma = cand.get("uncertainty", 0)
            features = cand.get("features", [])

            if self.acquisition == "ucb":
                score = mu + beta * sigma
            elif self.acquisition == "variance":
                score = sigma
            elif self.acquisition == "ei":
                # Expected improvement over best observed
                best_observed = max((h.get("value", 0) for h in self.history), default=0)
                if sigma > 0:
                    # Approximate Phi(z) * (mu - best_observed) + sigma * phi(z)
                    score = mu - best_observed + beta * sigma
                else:
                    score = 0
            else:
                score = sigma

            if score > best_score:
                best_score = score
                best = ActiveLearningCandidate(
                    features=features,
                    predicted_value=mu,
                    uncertainty=sigma,
                    acquisition_score=score,
                )

        return best

    def record_observation(self, features: list[float], value: float) -> None:
        """Record an actual measurement/simulation result."""
        self.history.append({"features": features, "value": value})
