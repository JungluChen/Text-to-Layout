"""Typed 3-D finite-element models, and their projections onto Gmsh and Palace."""

from __future__ import annotations

from textlayout.fem.model import (
    CriticalRegion,
    CriticalRegionKind,
    CriticalRegionType,
    FEM_MODEL_SCHEMA,
    EigenmodeSolve,
    FEMModel,
    FEMModelError,
    Interface,
    LocalRefinement,
    LumpedPort,
    Material,
    MeshControl,
    MeshRegion,
    MeshRegionKind,
    Surface,
    SurfaceKind,
    SurfaceRole,
    Volume,
    VolumeRole,
    WavePort,
)

__all__ = [
    "CriticalRegion",
    "CriticalRegionKind",
    "CriticalRegionType",
    "FEM_MODEL_SCHEMA",
    "EigenmodeSolve",
    "FEMModel",
    "FEMModelError",
    "Interface",
    "LocalRefinement",
    "LumpedPort",
    "Material",
    "MeshControl",
    "MeshRegion",
    "MeshRegionKind",
    "Surface",
    "SurfaceKind",
    "SurfaceRole",
    "Volume",
    "VolumeRole",
    "WavePort",
]
