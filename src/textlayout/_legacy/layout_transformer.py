"""Layout Transformer — encoder for GDS token sequences.

Transformer-based model that learns layout embeddings for:
    - Performance prediction (f0, Q, Z0, gain, BW)
    - Device similarity search
    - Inverse design (text → layout)
    - Self-supervised pre-training (masked token prediction)

Architecture:
    GDS tokens → Token embedding + positional encoding →
    Transformer encoder layers → [CLS] embedding → task heads

Uses PyTorch if available; falls back to a pure-numpy reference implementation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TransformerConfig:
    """Hyperparameters for the layout transformer."""
    vocab_size: int = 300
    max_seq_len: int = 4096
    d_model: int = 256
    n_heads: int = 8
    n_layers: int = 6
    d_ff: int = 1024
    dropout: float = 0.1
    n_performance_outputs: int = 8    # f0, Q, Z0, eps_eff, S11, S21, gain, BW
    pad_token_id: int = 0


# ---------------------------------------------------------------------------
# PyTorch implementation
# ---------------------------------------------------------------------------

if HAS_TORCH:

    class TokenEmbedding(nn.Module):
        def __init__(self, config: TransformerConfig):
            super().__init__()
            self.token_emb = nn.Embedding(config.vocab_size, config.d_model,
                                          padding_idx=config.pad_token_id)
            self.pos_emb = nn.Embedding(config.max_seq_len, config.d_model)
            self.layer_norm = nn.LayerNorm(config.d_model)
            self.dropout = nn.Dropout(config.dropout)

        def forward(self, token_ids: "torch.Tensor") -> "torch.Tensor":
            seq_len = token_ids.size(1)
            positions = torch.arange(seq_len, device=token_ids.device).unsqueeze(0)
            x = self.token_emb(token_ids) + self.pos_emb(positions)
            return self.dropout(self.layer_norm(x))

    class TransformerBlock(nn.Module):
        def __init__(self, config: TransformerConfig):
            super().__init__()
            self.attn = nn.MultiheadAttention(
                config.d_model, config.n_heads, dropout=config.dropout, batch_first=True
            )
            self.ff = nn.Sequential(
                nn.Linear(config.d_model, config.d_ff),
                nn.GELU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.d_ff, config.d_model),
                nn.Dropout(config.dropout),
            )
            self.norm1 = nn.LayerNorm(config.d_model)
            self.norm2 = nn.LayerNorm(config.d_model)

        def forward(self, x: "torch.Tensor", mask: "torch.Tensor | None" = None) -> "torch.Tensor":
            attn_out, _ = self.attn(x, x, x, key_padding_mask=mask)
            x = self.norm1(x + attn_out)
            x = self.norm2(x + self.ff(x))
            return x

    class LayoutTransformer(nn.Module):
        """Transformer encoder for GDS token sequences.

        Input:  token_ids  (batch, seq_len)  — integer token IDs
        Output: embedding  (batch, d_model)  — CLS-pooled layout representation
        """

        def __init__(self, config: TransformerConfig):
            super().__init__()
            self.config = config
            self.embedding = TokenEmbedding(config)
            self.encoder = nn.ModuleList(
                [TransformerBlock(config) for _ in range(config.n_layers)]
            )
            self.cls_proj = nn.Linear(config.d_model, config.d_model)

            # Task heads
            self.performance_head = nn.Sequential(
                nn.Linear(config.d_model, config.d_model),
                nn.GELU(),
                nn.Linear(config.d_model, config.n_performance_outputs),
            )
            self.similarity_head = nn.Linear(config.d_model, 128)

        def forward(
            self,
            token_ids: "torch.Tensor",
            attention_mask: "torch.Tensor | None" = None,
        ) -> dict[str, "torch.Tensor"]:
            # Build padding mask
            pad_mask = (token_ids == self.config.pad_token_id) if attention_mask is None else ~attention_mask.bool()

            x = self.embedding(token_ids)
            for layer in self.encoder:
                x = layer(x, mask=pad_mask)

            # CLS token output
            cls_emb = x[:, 0, :]
            cls_emb = self.cls_proj(cls_emb)

            return {
                "embedding": cls_emb,
                "performance": self.performance_head(cls_emb),
                "similarity": F.normalize(self.similarity_head(cls_emb), dim=-1),
                "sequence_output": x,
            }


# ---------------------------------------------------------------------------
# Numpy reference (no PyTorch dependency)
# ---------------------------------------------------------------------------

class NumpyLayoutTransformer:
    """Minimal transformer-like encoder using only numpy.

    Provides the same interface as the PyTorch version for environments
    where torch is not installed.
    """

    def __init__(self, config: TransformerConfig):
        self.config = config
        self._rng = np.random.RandomState(42)
        d = config.d_model

        # Xavier-init weight matrices
        scale = math.sqrt(2.0 / (config.vocab_size + d))
        self._token_emb = self._rng.randn(config.vocab_size, d) * scale
        self._pos_emb = self._rng.randn(config.max_seq_len, d) * scale

        # Transformer layer weights (simplified single-head self-attention)
        self._attn_w = self._rng.randn(d, d) * scale
        self._ff_w1 = self._rng.randn(d, config.d_ff) * math.sqrt(2.0 / (d + config.d_ff))
        self._ff_w2 = self._rng.randn(config.d_ff, d) * math.sqrt(2.0 / (config.d_ff + d))

        # Task heads
        self._perf_w = self._rng.randn(d, config.n_performance_outputs) * scale
        self._sim_w = self._rng.randn(d, 128) * scale

    def forward(
        self,
        token_ids: list[int],
        max_len: int = 0,
    ) -> dict[str, Any]:
        """Forward pass.  Returns numpy arrays."""
        max_len = max_len or self.config.max_seq_len
        ids = np.array(token_ids[:max_len], dtype=np.int64)
        seq_len = len(ids)

        # Embedding
        x = self._token_emb[ids] + self._pos_emb[:seq_len]

        # Simplified self-attention (single head, no masking)
        attn_scores = x @ self._attn_w
        attn_weights = np.exp(attn_scores - attn_scores.max(axis=-1, keepdims=True))
        attn_weights = attn_weights / (attn_weights.sum(axis=-1, keepdims=True) + 1e-8)
        attn_out = np.sum(attn_weights * x, axis=-2) if len(attn_weights.shape) > 2 else x.mean(axis=-2)

        # FFN
        h = np.maximum(0, attn_out @ self._ff_w1)  # ReLU
        out = h @ self._ff_w2

        # CLS-like pooling (mean pooling)
        emb = out.mean(axis=0) if out.ndim > 1 else out

        # Task heads
        perf = emb @ self._perf_w
        sim_raw = emb @ self._sim_w
        sim = sim_raw / (np.linalg.norm(sim_raw) + 1e-8)

        return {
            "embedding": emb,
            "performance": perf,
            "similarity": sim,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_layout_transformer(config: TransformerConfig | None = None) -> Any:
    """Create a layout transformer using the best available backend.

    Returns a PyTorch nn.Module if torch is available, otherwise a numpy fallback.
    """
    config = config or TransformerConfig()
    if HAS_TORCH:
        return LayoutTransformer(config)
    return NumpyLayoutTransformer(config)


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

PERFORMANCE_LABELS = [
    "frequency_ghz",
    "quality_factor_log",
    "impedance_ohm",
    "effective_permittivity",
    "s11_db",
    "s21_db",
    "gain_db",
    "bandwidth_mhz",
]


def decode_performance(raw: Any) -> dict[str, float]:
    """Convert raw model output to named performance dict."""
    if HAS_TORCH and hasattr(raw, "detach"):
        raw = raw.detach().cpu().numpy()
    if isinstance(raw, dict):
        raw = raw.get("performance", raw)
    raw = np.asarray(raw).flatten()
    result: dict[str, float] = {}
    for i, label in enumerate(PERFORMANCE_LABELS):
        if i < len(raw):
            val = float(raw[i])
            if "log" in label:
                val = math.exp(val)
            result[label] = round(val, 4)
    return result


def predict_from_tokens(
    token_ids: list[int],
    model: Any | None = None,
    config: TransformerConfig | None = None,
) -> dict[str, Any]:
    """Run inference on a token sequence and return predictions."""
    config = config or TransformerConfig()
    if model is None:
        model = create_layout_transformer(config)

    if HAS_TORCH and hasattr(model, "forward"):
        tensor = torch.tensor([token_ids], dtype=torch.long)
        with torch.no_grad():
            out = model(tensor)
        return {
            "performance": decode_performance(out["performance"].numpy()),
            "similarity": out["similarity"].numpy().tolist(),
            "backend": "torch",
        }
    else:
        out = model.forward(token_ids)
        return {
            "performance": decode_performance(out["performance"]),
            "similarity": out["similarity"].tolist() if isinstance(out["similarity"], np.ndarray) else out["similarity"],
            "backend": "numpy",
        }
