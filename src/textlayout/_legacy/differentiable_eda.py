"""Differentiable EDA — PyTorch-based geometry optimization.

Implements:
    - Differentiable geometry engine (rectangle, path, polygon)
    - PyTorch GDS parameter representation
    - Differentiable PCell (parameters → GDS → performance)
    - Gradient-based optimization (adjoint-like)
    - Topology optimization primitives
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from importlib.util import find_spec

HAS_NUMPY = find_spec("numpy") is not None


# ---------------------------------------------------------------------------
# Differentiable geometry primitives
# ---------------------------------------------------------------------------

@dataclass
class DiffRectangle:
    """A differentiable rectangle parameterised by center + size."""
    cx: float = 0.0
    cy: float = 0.0
    width: float = 1.0
    height: float = 1.0
    layer: int = 3
    datatype: int = 0

    if HAS_TORCH:
        def as_tensor(self) -> "torch.Tensor":
            return torch.tensor(
                [self.cx, self.cy, self.width, self.height],
                dtype=torch.float64,
                requires_grad=True,
            )

        @classmethod
        def from_tensor(cls, t: "torch.Tensor", layer: int = 3) -> "DiffRectangle":
            return cls(
                cx=float(t[0]), cy=float(t[1]),
                width=float(t[2]), height=float(t[3]),
                layer=layer,
            )


@dataclass
class DiffCPW:
    """Differentiable coplanar waveguide: width, gap, length."""
    width: float = 10.0
    gap: float = 6.0
    length: float = 100.0
    layer: int = 6
    datatype: int = 0

    if HAS_TORCH:
        def as_tensor(self) -> "torch.Tensor":
            return torch.tensor(
                [self.width, self.gap, self.length],
                dtype=torch.float64,
                requires_grad=True,
            )

        @classmethod
        def from_tensor(cls, t: "torch.Tensor", layer: int = 6) -> "DiffCPW":
            return cls(
                width=float(t[0]), gap=float(t[1]), length=float(t[2]),
                layer=layer,
            )


@dataclass
class DiffJunction:
    """Differentiable Josephson junction: area, critical current density."""
    width: float = 0.22
    height: float = 0.22
    jc_ua_per_um2: float = 2.0
    layer: int = 4
    datatype: int = 0

    @property
    def area_um2(self) -> float:
        return self.width * self.height

    @property
    def critical_current_ua(self) -> float:
        return self.area_um2 * self.jc_ua_per_um2

    if HAS_TORCH:
        def as_tensor(self) -> "torch.Tensor":
            return torch.tensor(
                [self.width, self.height, self.jc_ua_per_um2],
                dtype=torch.float64,
                requires_grad=True,
            )

        @classmethod
        def from_tensor(cls, t: "torch.Tensor") -> "DiffJunction":
            return cls(
                width=float(t[0]), height=float(t[1]),
                jc_ua_per_um2=float(t[2]),
            )


# ---------------------------------------------------------------------------
# Differentiable PCell
# ---------------------------------------------------------------------------

class DiffPCell:
    """A parametric cell where geometry parameters are differentiable.

    Wraps geometry primitives and maps parameters → GDS shapes.
    Supports gradient-based optimization through the parameter → shape → performance chain.
    """

    def __init__(self, name: str = "diff_pcell"):
        self.name = name
        self._params: dict[str, Any] = {}
        self._shapes: list[Any] = []

    def set_params(self, **kwargs: float) -> None:
        self._params.update(kwargs)

    def get_tensor_params(self) -> "torch.Tensor | None":
        if not HAS_TORCH:
            return None
        values = [v for v in self._params.values() if isinstance(v, (int, float))]
        return torch.tensor(values, dtype=torch.float64, requires_grad=True)

    def build_jj(self, width: float = 0.22, height: float = 0.22) -> DiffRectangle:
        shape = DiffRectangle(cx=0, cy=0, width=width, height=height, layer=4)
        self._shapes.append(shape)
        self._params["jj_width"] = width
        self._params["jj_height"] = height
        return shape

    def build_cpw(
        self, width: float = 10.0, gap: float = 6.0, length: float = 100.0
    ) -> DiffCPW:
        shape = DiffCPW(width=width, gap=gap, length=length, layer=6)
        self._shapes.append(shape)
        self._params["cpw_width"] = width
        self._params["cpw_gap"] = gap
        self._params["cpw_length"] = length
        return shape

    def build_capacitor(
        self, fingers: int = 4, finger_width: float = 2.0,
        finger_length: float = 20.0, gap: float = 1.0,
    ) -> dict[str, float]:
        area = fingers * finger_width * finger_length
        cap_ff = area * 0.001  # rough fF estimate
        self._params["idc_fingers"] = fingers
        self._params["idc_finger_width"] = finger_width
        self._params["idc_finger_length"] = finger_length
        self._params["idc_gap"] = gap
        self._params["idc_capacitance_ff"] = cap_ff
        return {"area_um2": area, "capacitance_fF": cap_ff}

    def shapes(self) -> list[Any]:
        return self._shapes

    def params(self) -> dict[str, Any]:
        return dict(self._params)


# ---------------------------------------------------------------------------
# Differentiable performance model
# ---------------------------------------------------------------------------

if HAS_TORCH:

    class DiffJPAModel(nn.Module):
        """Differentiable JPA gain/bandwidth model.

        Maps geometric parameters to predicted performance.
        Trained from HFSS/simulation data or using analytical formulas.
        """

        def __init__(self, input_dim: int = 8, hidden_dim: int = 32):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.Tanh(),
                nn.Linear(hidden_dim, 4),  # f0, Q, gain, BW
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.net(x)

    class DiffTopologyOptimizer:
        """Gradient-based topology optimization for quantum circuits.

        Usage::

            optimizer = DiffTopologyOptimizer()
            result = optimizer.optimize(
                initial_params={"cpw_width": 10, "cpw_gap": 6, "jj_width": 0.22},
                target={"frequency_ghz": 5.0, "gain_db": 20.0},
                n_steps=100,
            )
        """

        def __init__(self, model: "nn.Module | None" = None):
            self.model = model or DiffJPAModel()

        def optimize(
            self,
            initial_params: dict[str, float],
            target: dict[str, float],
            n_steps: int = 100,
            lr: float = 0.01,
        ) -> dict[str, Any]:
            """Run gradient-based optimization."""
            # Build parameter tensor
            param_values = list(initial_params.values())
            params = torch.tensor(param_values, dtype=torch.float64, requires_grad=True)

            target_tensor = torch.tensor(
                [target.get(k, 0) for k in ["frequency_ghz", "quality_factor", "gain_db", "bandwidth_mhz"]],
                dtype=torch.float64,
            )

            optimizer = torch.optim.Adam([params], lr=lr)
            history: list[dict[str, float]] = []

            for step in range(n_steps):
                optimizer.zero_grad()
                pred = self.model(params.float())
                loss = ((pred - target_tensor) ** 2).sum()
                loss.backward()
                optimizer.step()

                if step % 10 == 0:
                    history.append({
                        "step": step,
                        "loss": float(loss.item()),
                        "params": {k: float(v) for k, v in zip(initial_params.keys(), params.detach())},
                    })

            final_params = {k: float(v) for k, v in zip(initial_params.keys(), params.detach())}
            return {
                "status": "optimized",
                "final_params": final_params,
                "final_loss": float(loss.item()),
                "history": history,
                "n_steps": n_steps,
            }

    class DiffInverseDesigner:
        """Inverse design: target specs → geometry parameters.

        Uses the differentiable model in reverse: given desired performance,
        find geometry parameters that produce it.
        """

        def __init__(self, model: "nn.Module | None" = None):
            self.model = model or DiffJPAModel()

        def design(
            self,
            target: dict[str, float],
            param_bounds: dict[str, tuple[float, float]] | None = None,
            n_iterations: int = 200,
            lr: float = 0.005,
        ) -> dict[str, Any]:
            """Find geometry parameters for target performance."""
            n_params = 8  # fixed for now
            params = torch.rand(n_params, dtype=torch.float64, requires_grad=True)

            target_vals = [target.get(k, 0) for k in [
                "frequency_ghz", "quality_factor", "gain_db", "bandwidth_mhz"
            ]]
            target_tensor = torch.tensor(target_vals, dtype=torch.float64)

            optimizer = torch.optim.Adam([params], lr=lr)

            for _ in range(n_iterations):
                optimizer.zero_grad()
                pred = self.model(params.float())
                loss = ((pred - target_tensor) ** 2).sum()
                loss.backward()
                optimizer.step()

                # Apply bounds
                if param_bounds:
                    with torch.no_grad():
                        for i, (lo, hi) in enumerate(param_bounds.values()):
                            if i < len(params):
                                params.data[i] = torch.clamp(params.data[i], lo, hi)

            return {
                "status": "designed",
                "parameters": params.detach().tolist(),
                "predicted": self.model(params.detach().float()).tolist(),
                "target": target,
                "loss": float(loss.item()),
            }

else:
    class DiffTopologyOptimizer:  # type: ignore[no-redef]
        def __init__(self, **kw: Any):
            pass
        def optimize(self, **kw: Any) -> dict[str, Any]:
            return {"status": "skipped", "message": "PyTorch not available"}

    class DiffInverseDesigner:  # type: ignore[no-redef]
        def __init__(self, **kw: Any):
            pass
        def design(self, **kw: Any) -> dict[str, Any]:
            return {"status": "skipped", "message": "PyTorch not available"}


# ---------------------------------------------------------------------------
# Analytical differentiable JPA model (numpy)
# ---------------------------------------------------------------------------

def analytical_jpa_gain(
    junction_area_um2: float,
    jc_ua_per_um2: float,
    pump_current_ua: float,
    resonator_frequency_ghz: float,
    coupling_capacitance_fF: float,
    shunt_capacitance_fF: float,
) -> dict[str, float]:
    """Analytical JPA gain model (Kerr parametric amplifier).

    Uses the standard pump-dependent gain formula:
        G = 1 + (pump_current / threshold_current)^2
    """
    ic_ua = junction_area_um2 * jc_ua_per_um2
    threshold_ua = ic_ua * 0.5  # typical threshold
    pump_ratio = pump_current_ua / threshold_ua if threshold_ua > 0 else 0

    gain_lin = 1 + pump_ratio ** 2
    gain_db = 20 * math.log10(gain_lin) if gain_lin > 0 else 0

    # Bandwidth estimate
    total_c = coupling_capacitance_fF + shunt_capacitance_fF
    bw_mhz = resonator_frequency_ghz * 1000 / (2 * math.pi * total_c * 0.001) if total_c > 0 else 0

    return {
        "gain_db": round(gain_db, 2),
        "bandwidth_mhz": round(bw_mhz, 2),
        "critical_current_ua": round(ic_ua, 6),
        "threshold_current_ua": round(threshold_ua, 6),
    }
