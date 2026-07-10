"""GDS Tokenizer — convert GDSII layout into discrete tokens for ML.

Tokenises polygons, paths, labels, and ports from GDS layers into integer
sequences suitable for transformer input.  The vocabulary is layer-based
with geometry-type prefixes.

Token schema:
    [LAYER_PURPOSE] TYPE x y w h   — rectangle
    [LAYER_PURPOSE] PATH x0 y0 x1 y1 w   — path
    [LAYER_PURPOSE] LABEL x y text   — text label
    [PORT] x y layer purpose impedance   — port

Every numeric coordinate is quantised to a configurable grid (default 1 nm).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import klayout.db as kdb
except ImportError:
    kdb = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Token vocabulary
# ---------------------------------------------------------------------------

_SPECIAL_TOKENS: dict[str, int] = {
    "<PAD>": 0,
    "<UNK>": 1,
    "<CLS>": 2,
    "<SEP>": 3,
    "<MASK>": 4,
    "<PORT>": 5,
    "<LABEL>": 6,
    "<JJ>": 7,
    "<SQUID>": 8,
    "<CPW>": 9,
    "<IDC>": 10,
    "<VIA>": 11,
    "<GROUND>": 12,
    "<RESONATOR>": 13,
}

_GEOMETRY_TOKENS: dict[str, int] = {
    "RECT": 20,
    "PATH": 21,
    "POLYGON": 22,
    "LABEL": 23,
    "PORT": 24,
}

# Layer names are mapped to token IDs starting at 100.
_LAYER_OFFSET = 100


@dataclass
class Token:
    """A single token in the layout sequence."""
    token_id: int
    token_str: str
    category: str = "geometry"      # special, geometry, layer, coord
    value: float | None = None
    position: int = 0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.token_id, "str": self.token_str}
        if self.value is not None:
            d["value"] = self.value
        return d


@dataclass
class TokenSequence:
    """A complete tokenised layout."""
    tokens: list[Token] = field(default_factory=list)
    layer_map: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ids(self) -> list[int]:
        return [t.token_id for t in self.tokens]

    def __len__(self) -> int:
        return len(self.tokens)

    def to_dict(self) -> dict[str, Any]:
        return {
            "length": len(self.tokens),
            "tokens": [t.to_dict() for t in self.tokens[:50]],  # first 50 for preview
            "layer_map": self.layer_map,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class GDSTokenizer:
    """Convert GDS polygons into integer token sequences.

    Parameters
    ----------
    grid_nm : Quantisation grid in nanometres (default 1 nm).
    max_tokens : Maximum token sequence length (truncates long layouts).
    """

    def __init__(self, grid_nm: float = 1.0, max_tokens: int = 4096):
        self.grid_nm = grid_nm
        self.max_tokens = max_tokens
        self._layer_counter = 0
        self._layer_vocab: dict[tuple[int, int], int] = {}
        self._reverse_layer_vocab: dict[int, tuple[int, int]] = {}

    def _get_layer_token(self, layer: int, purpose: int) -> int:
        """Map a GDS (layer, purpose) pair to a token ID."""
        key = (layer, purpose)
        if key not in self._layer_vocab:
            tid = _LAYER_OFFSET + self._layer_counter
            self._layer_vocab[key] = tid
            self._reverse_layer_vocab[tid] = key
            self._layer_counter += 1
        return self._layer_vocab[key]

    def _quantise(self, value_um: float) -> float:
        """Quantise a micron value to the grid."""
        return round(value_um * 1000 / self.grid_nm) * self.grid_nm / 1000

    def _quantise_coord(self, x_um: float, y_um: float) -> tuple[float, float]:
        return self._quantise(x_um), self._quantise(y_um)

    def tokenize_gds(self, gds_path: str | Path) -> TokenSequence:
        """Tokenise a GDS file."""
        if kdb is None:
            return self._tokenize_sidecar_fallback(gds_path)
        return self._tokenize_klayout(gds_path)

    def tokenize_sidecar(self, sidecar_path: str | Path) -> TokenSequence:
        """Tokenise from a semantic sidecar JSON (no klayout needed)."""
        return self._tokenize_sidecar_fallback(sidecar_path)

    # -- klayout path --------------------------------------------------------

    def _tokenize_klayout(self, gds_path: str | Path) -> TokenSequence:
        layout = kdb.Layout()
        layout.read(str(gds_path))
        seq = TokenSequence()
        seq.tokens.append(Token(_SPECIAL_TOKENS["<CLS>"], "<CLS>", "special"))

        for cell in layout.each_cell():
            for inst in cell.each_inst():
                layout_obj = inst.cell
                for layer_idx in layout_obj.layers():
                    for shape in layout_obj.begin_shapes_rec(layer_idx):
                        layer = shape.layer
                        dt = shape.datatype
                        layer_token = self._get_layer_token(layer, dt)
                        seq.tokens.append(Token(layer_token, f"[{layer}_{dt}]", "layer"))

                        if shape.is_box():
                            bbox = shape.bbox()
                            x1, y1 = self._quantise_coord(bbox.left * layout.dbu, bbox.top * layout.dbu)
                            x2, y2 = self._quantise_coord(bbox.right * layout.dbu, bbox.bottom * layout.dbu)
                            w = x2 - x1
                            h = y2 - y1
                            seq.tokens.append(Token(_GEOMETRY_TOKENS["RECT"], "RECT", "geometry"))
                            seq.tokens.append(Token(0, f"{x1:.3f}", "coord", x1))
                            seq.tokens.append(Token(0, f"{y1:.3f}", "coord", y1))
                            seq.tokens.append(Token(0, f"{w:.3f}", "coord", w))
                            seq.tokens.append(Token(0, f"{h:.3f}", "coord", h))

                        elif shape.is_path():
                            path = shape.path
                            pts = [self._quantise_coord(p.x * layout.dbu, p.y * layout.dbu)
                                   for p in path.polygon().each_point()]
                            w = path.width * layout.dbu
                            seq.tokens.append(Token(_GEOMETRY_TOKENS["PATH"], "PATH", "geometry"))
                            for px, py in pts[:10]:
                                seq.tokens.append(Token(0, f"{px:.3f}", "coord", px))
                                seq.tokens.append(Token(0, f"{py:.3f}", "coord", py))

                        elif shape.is_polygon():
                            poly = shape.polygon
                            pts = [self._quantise_coord(p.x * layout.dbu, p.y * layout.dbu)
                                   for p in poly.each_point()]
                            seq.tokens.append(Token(_GEOMETRY_TOKENS["POLYGON"], "POLYGON", "geometry"))
                            for px, py in pts[:10]:
                                seq.tokens.append(Token(0, f"{px:.3f}", "coord", px))
                                seq.tokens.append(Token(0, f"{py:.3f}", "coord", py))

            for label in cell.each_text():
                seq.tokens.append(Token(_GEOMETRY_TOKENS["LABEL"], "LABEL", "geometry"))
                seq.tokens.append(Token(0, f"{label.x * layout.dbu:.3f}", "coord", label.x * layout.dbu))
                seq.tokens.append(Token(0, f"{label.y * layout.dbu:.3f}", "coord", label.y * layout.dbu))

        seq.tokens.append(Token(_SPECIAL_TOKENS["<SEP>"], "<SEP>", "special"))
        seq.layer_map = {str(k): v for k, v in self._layer_vocab.items()}
        seq.metadata = {
            "source": str(gds_path),
            "grid_nm": self.grid_nm,
            "num_layers": self._layer_counter,
        }
        return seq

    # -- sidecar fallback (no klayout) ---------------------------------------

    def _tokenize_sidecar_fallback(self, path: str | Path) -> TokenSequence:
        """Build tokens from sidecar JSON or generate a minimal sequence."""
        seq = TokenSequence()
        seq.tokens.append(Token(_SPECIAL_TOKENS["<CLS>"], "<CLS>", "special"))

        p = Path(path)
        if p.suffix == ".json" and p.exists():
            try:
                data = json.loads(p.read_text())
                ports = data.get("ports", [])
                layers = data.get("layers", [])
                bbox = data.get("bounding_box", [])

                for layer_entry in layers:
                    layer_num = layer_entry.get("layer", [0, 0])
                    if isinstance(layer_num, list) and len(layer_num) >= 2:
                        lt = self._get_layer_token(layer_num[0], layer_num[1])
                    else:
                        lt = self._get_layer_token(0, 0)
                    seq.tokens.append(Token(lt, f"[{layer_num}]", "layer"))

                    name = layer_entry.get("name", "M1")
                    name_lower = name.lower()
                    if "jj" in name_lower or "junction" in name_lower:
                        seq.tokens.append(Token(_SPECIAL_TOKENS["<JJ>"], "<JJ>", "special"))
                    elif "cpw" in name_lower or "waveguide" in name_lower:
                        seq.tokens.append(Token(_SPECIAL_TOKENS["<CPW>"], "<CPW>", "special"))
                    elif "idc" in name_lower or "cap" in name_lower:
                        seq.tokens.append(Token(_SPECIAL_TOKENS["<IDC>"], "<IDC>", "special"))
                    elif "via" in name_lower:
                        seq.tokens.append(Token(_SPECIAL_TOKENS["<VIA>"], "<VIA>", "special"))
                    elif "ground" in name_lower or "gnd" in name_lower:
                        seq.tokens.append(Token(_SPECIAL_TOKENS["<GROUND>"], "<GROUND>", "special"))
                    elif "resonator" in name_lower:
                        seq.tokens.append(Token(_SPECIAL_TOKENS["<RESONATOR>"], "<RESONATOR>", "special"))

                for port in ports:
                    seq.tokens.append(Token(_SPECIAL_TOKENS["<PORT>"], "<PORT>", "special"))
                    center = port.get("center", [0, 0])
                    seq.tokens.append(Token(0, f"{center[0]:.3f}", "coord", center[0]))
                    seq.tokens.append(Token(0, f"{center[1]:.3f}", "coord", center[1]))
                    port_layer = port.get("layer", [3, 0])
                    if isinstance(port_layer, list) and len(port_layer) >= 2:
                        seq.tokens.append(Token(self._get_layer_token(port_layer[0], port_layer[1]),
                                                f"[{port_layer}]", "layer"))

                if bbox and len(bbox) >= 2:
                    seq.tokens.append(Token(0, f"bbox_w:{bbox[0]:.1f}", "coord", bbox[0]))
                    seq.tokens.append(Token(0, f"bbox_h:{bbox[1]:.1f}", "coord", bbox[1]))

            except (json.JSONDecodeError, KeyError):
                pass

        seq.tokens.append(Token(_SPECIAL_TOKENS["<SEP>"], "<SEP>", "special"))
        seq.layer_map = {str(k): v for k, v in self._layer_vocab.items()}
        seq.metadata = {
            "source": str(path),
            "grid_nm": self.grid_nm,
            "num_layers": self._layer_counter,
            "fallback": True,
        }
        return seq

    # -- vocabulary -----------------------------------------------------------

    @property
    def vocab_size(self) -> int:
        return _LAYER_OFFSET + self._layer_counter + 20

    def decode_token(self, token_id: int) -> str:
        """Map a token ID back to a human-readable string."""
        for name, tid in _SPECIAL_TOKENS.items():
            if tid == token_id:
                return name
        for name, tid in _GEOMETRY_TOKENS.items():
            if tid == token_id:
                return name
        if token_id in self._reverse_layer_vocab:
            layer, dt = self._reverse_layer_vocab[token_id]
            return f"[L{layer}_D{dt}]"
        return f"<{token_id}>"

    def special_token(self, name: str) -> int:
        return _SPECIAL_TOKENS.get(name, _SPECIAL_TOKENS["<UNK>"])

    def pad_token_id(self) -> int:
        return _SPECIAL_TOKENS["<PAD>"]

    def cls_token_id(self) -> int:
        return _SPECIAL_TOKENS["<CLS>"]

    def sep_token_id(self) -> int:
        return _SPECIAL_TOKENS["<SEP>"]

    def mask_token_id(self) -> int:
        return _SPECIAL_TOKENS["<MASK>"]
