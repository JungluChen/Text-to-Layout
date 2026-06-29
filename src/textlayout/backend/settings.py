"""Backend settings, sourced from environment variables (no global state)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration for the plugin server."""

    host: str = "127.0.0.1"
    port: int = 8000
    workspace: Path = Path("workspace/textlayout")
    title: str = "Text-to-Layout Plugin API"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.environ.get("TEXTLAYOUT_HOST", "127.0.0.1"),
            port=int(os.environ.get("TEXTLAYOUT_PORT", "8000")),
            workspace=Path(os.environ.get("TEXTLAYOUT_WORKSPACE", "workspace/textlayout")),
        )
