"""Typed external ParaView integration for Palace visualization artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from textlayout.evidence.canonical import sha256_file


class PalaceVisualizationKind(str, Enum):
    AMR_ERROR_INDICATOR = "amr_error_indicator"
    ELECTRIC_ENERGY_DENSITY = "electric_energy_density"
    MAGNETIC_ENERGY_DENSITY = "magnetic_energy_density"
    MESH_QUALITY = "mesh_quality"
    TARGET_MODE_LOCALIZATION = "target_mode_localization"


class ParaViewIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    executable: Path
    executable_sha256: str = Field(min_length=64, max_length=64)


class ParaViewRenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: PalaceVisualizationKind
    command: list[str]
    return_code: int
    input_sha256: str
    image_path: Path
    image_sha256: str | None = None
    metadata_path: Path


def command_hash(command: list[str]) -> str:
    encoded = json.dumps(command, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def render_palace_view(
    identity: ParaViewIdentity,
    script: Path,
    source: Path,
    output: Path,
    kind: PalaceVisualizationKind,
    *,
    timeout_seconds: float = 600,
) -> ParaViewRenderResult:
    """Execute one retained pvpython batch render through file exchange."""
    source = source.resolve()
    output = output.resolve()
    metadata = output.with_suffix(".json")
    command = [
        str(identity.executable),
        str(script.resolve()),
        "--input",
        str(source),
        "--output",
        str(output),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    image_hash = sha256_file(output) if output.is_file() else None
    result = ParaViewRenderResult(
        kind=kind,
        command=command,
        return_code=completed.returncode,
        input_sha256=sha256_file(source),
        image_path=output,
        image_sha256=image_hash,
        metadata_path=metadata,
    )
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(
            {
                **result.model_dump(mode="json"),
                "command_sha256": command_hash(command),
                "pvpython_sha256": identity.executable_sha256,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result

