"""Device Prediction — predict EM parameters from layout tokens.

Wraps the layout transformer and tokenizer into a single inference pipeline
that takes a GDS file or sidecar and returns predicted electromagnetic
performance without running HFSS/openEMS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from text_to_gds.gds_tokenizer import GDSTokenizer, TokenSequence
from text_to_gds.layout_transformer import (
    TransformerConfig,
    create_layout_transformer,
    predict_from_tokens,
)


# ---------------------------------------------------------------------------
# Prediction result
# ---------------------------------------------------------------------------

@dataclass
class DevicePrediction:
    """Predicted performance for a quantum device layout."""
    device_id: str = ""
    source_path: str = ""
    predicted: dict[str, float] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    similar_devices: list[dict[str, Any]] = field(default_factory=list)
    model_backend: str = "numpy"
    token_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "source_path": self.source_path,
            "predicted": self.predicted,
            "confidence": self.confidence,
            "similar_devices": self.similar_devices,
            "model_backend": self.model_backend,
            "token_count": self.token_count,
        }


# ---------------------------------------------------------------------------
# Prediction pipeline
# ---------------------------------------------------------------------------

class DevicePredictor:
    """End-to-end predictor: GDS → tokens → transformer → EM parameters.

    Usage::

        predictor = DevicePredictor()
        result = predictor.predict_from_gds("workspace/artifacts/my_device.gds")
        result = predictor.predict_from_sidecar("workspace/artifacts/my_device.sidecar.json")
    """

    def __init__(
        self,
        config: TransformerConfig | None = None,
        tokenizer: GDSTokenizer | None = None,
        model: Any | None = None,
    ):
        self.config = config or TransformerConfig()
        self.tokenizer = tokenizer or GDSTokenizer()
        self.model = model or create_layout_transformer(self.config)

    def predict_from_gds(
        self,
        gds_path: str | Path,
        device_id: str = "",
    ) -> DevicePrediction:
        """Tokenise a GDS file and predict performance."""
        seq = self.tokenizer.tokenize_gds(gds_path)
        return self._predict(seq, gds_path, device_id)

    def predict_from_sidecar(
        self,
        sidecar_path: str | Path,
        device_id: str = "",
    ) -> DevicePrediction:
        """Tokenise from a sidecar JSON and predict performance."""
        seq = self.tokenizer.tokenize_sidecar(sidecar_path)
        return self._predict(seq, sidecar_path, device_id)

    def predict_from_tokens(
        self,
        token_ids: list[int],
        device_id: str = "",
    ) -> DevicePrediction:
        """Predict from a raw token ID list."""
        result = predict_from_tokens(token_ids, self.model, self.config)
        perf = result.get("performance", {})
        return DevicePrediction(
            device_id=device_id,
            predicted=perf,
            confidence=self._estimate_confidence(perf),
            model_backend=result.get("backend", "unknown"),
            token_count=len(token_ids),
        )

    def batch_predict(
        self,
        paths: list[str | Path],
    ) -> list[DevicePrediction]:
        """Predict for multiple GDS/sidecar files."""
        results = []
        for p in paths:
            p_path = Path(p)
            if p_path.suffix == ".gds":
                results.append(self.predict_from_gds(p))
            else:
                results.append(self.predict_from_sidecar(p))
        return results

    # -- internal ------------------------------------------------------------

    def _predict(
        self,
        seq: TokenSequence,
        source_path: str | Path,
        device_id: str,
    ) -> DevicePrediction:
        ids = seq.ids
        result = predict_from_tokens(ids, self.model, self.config)
        perf = result.get("performance", {})
        return DevicePrediction(
            device_id=device_id or Path(source_path).stem,
            source_path=str(source_path),
            predicted=perf,
            confidence=self._estimate_confidence(perf),
            model_backend=result.get("backend", "unknown"),
            token_count=len(ids),
        )

    def _estimate_confidence(self, perf: dict[str, float]) -> dict[str, float]:
        """Heuristic confidence based on output magnitudes."""
        conf: dict[str, float] = {}
        for key, val in perf.items():
            # Simple heuristic: values closer to typical ranges get higher confidence
            if "frequency" in key:
                conf[key] = min(1.0, 1.0 - abs(val - 5.0) / 10.0) if val > 0 else 0.5
            elif "quality" in key:
                conf[key] = min(1.0, val / 10000) if val > 0 else 0.3
            elif "impedance" in key:
                conf[key] = min(1.0, 1.0 - abs(val - 50) / 100) if val > 0 else 0.5
            elif "gain" in key:
                conf[key] = min(1.0, val / 30) if val > 0 else 0.3
            else:
                conf[key] = 0.5
        return conf

    def save_model(self, path: str | Path) -> None:
        """Save model weights (torch) or numpy arrays."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(self.model, "state_dict"):
            import torch
            torch.save(self.model.state_dict(), path)
        else:
            import numpy as np
            state = {
                "config": self.config.__dict__,
                "_token_emb": self.model._token_emb,
                "_pos_emb": self.model._pos_emb,
                "_attn_w": self.model._attn_w,
                "_ff_w1": self.model._ff_w1,
                "_ff_w2": self.model._ff_w2,
                "_perf_w": self.model._perf_w,
                "_sim_w": self.model._sim_w,
            }
            np.savez(path, **state)

    def load_model(self, path: str | Path) -> None:
        """Load model weights."""
        path = Path(path)
        if hasattr(self.model, "load_state_dict"):
            import torch
            state = torch.load(path, map_location="cpu", weights_only=True)
            self.model.load_state_dict(state)
        else:
            import numpy as np
            data = np.load(path, allow_pickle=True)
            self.model._token_emb = data["_token_emb"]
            self.model._pos_emb = data["_pos_emb"]
            self.model._attn_w = data["_attn_w"]
            self.model._ff_w1 = data["_ff_w1"]
            self.model._ff_w2 = data["_ff_w2"]
            self.model._perf_w = data["_perf_w"]
            self.model._sim_w = data["_sim_w"]
