"""Stable source-checkout and installed-package resource paths."""

from __future__ import annotations

import os
from pathlib import Path


def repository_root() -> Path:
    """Locate the checkout without depending on the process working directory."""
    override = os.environ.get("TEXTLAYOUT_REPOSITORY_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Resolve repository resources, falling back to wheel package data."""
    checkout = repository_root().joinpath(*parts)
    if checkout.exists():
        return checkout
    return Path(__file__).resolve().parent.joinpath("data", *parts)
