"""FastAPI plugin server (driver layer). Delegates to the shared workflow core."""

from __future__ import annotations

from textlayout.backend.app import create_app
from textlayout.backend.settings import Settings

__all__ = ["Settings", "create_app"]
