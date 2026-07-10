"""Geometry IO, boolean, and extraction helpers."""

from textlayout._legacy.geometry.extraction import extract_layer_features
from textlayout._legacy.geometry.polygon import layer_regions, load_layout, summarize_layers

__all__ = ["extract_layer_features", "layer_regions", "load_layout", "summarize_layers"]
