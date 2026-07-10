"""Typed 3-D finite-element models, and their projections onto Gmsh and Palace."""

from __future__ import annotations

from textlayout.fem.model import (
    FEM_MODEL_SCHEMA,
    EigenmodeSolve,
    FEMModel,
    FEMModelError,
    Interface,
    LocalRefinement,
    LumpedPort,
    Material,
    MeshControl,
    Surface,
    SurfaceKind,
    Volume,
    VolumeRole,
    WavePort,
)

__all__ = [
    "FEM_MODEL_SCHEMA",
    "EigenmodeSolve",
    "FEMModel",
    "FEMModelError",
    "Interface",
    "LocalRefinement",
    "LumpedPort",
    "Material",
    "MeshControl",
    "Surface",
    "SurfaceKind",
    "Volume",
    "VolumeRole",
    "WavePort",
]
