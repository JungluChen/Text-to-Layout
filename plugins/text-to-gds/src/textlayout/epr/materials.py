"""Material / interface loss database for coherence estimation.

**Every default value here is ILLUSTRATIVE, not foundry-calibrated.** The
numbers are order-of-magnitude typical values from the published cQED surface-
loss literature (Wenner et al., APL 99, 113513 (2011); Wang et al., APL 107,
162601 (2015); McRae et al., Rev. Sci. Instrum. 91, 091101 (2020)). Real design
signoff requires loss tangents measured on the actual fabrication process —
that is exactly what the measurement-calibration loop is for.

The database is data, not logic: a foundry can ship its own JSON/YAML with the
same schema and the coherence math is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

MATERIALS_SCHEMA = "textlayout.loss-materials.v1"

#: Built-in illustrative materials DB files, mirroring knowledge/pdks/.
MATERIALS_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "materials"

#: Calibration provenance labels.
CALIBRATION_ILLUSTRATIVE = "illustrative_literature_range"
CALIBRATION_MEASURED = "measured_on_process"


class LossChannel(BaseModel):
    """One lossy dielectric region or interface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        description="Channel id: substrate | metal_substrate | metal_air | "
        "substrate_air | junction_dielectric"
    )
    material: str = Field(description="Human-readable material, e.g. 'high-resistivity Si'.")
    tan_delta: float = Field(gt=0.0, description="Loss tangent (dimensionless).")
    thickness_nm: float | None = Field(
        default=None, gt=0.0, description="Interface thickness for thin-film channels (nm)."
    )
    epsilon_r: float | None = Field(default=None, gt=0.0, description="Relative permittivity.")
    calibration: str = Field(
        default=CALIBRATION_ILLUSTRATIVE,
        description="illustrative_literature_range | measured_on_process",
    )
    source: str = Field(description="Citation or measurement record for tan_delta.")


class MaterialsDB(BaseModel):
    """A named set of loss channels used by one EPR/coherence analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default=MATERIALS_SCHEMA)
    name: str
    channels: dict[str, LossChannel]
    notes: list[str] = Field(default_factory=list)

    def channel(self, name: str) -> LossChannel:
        try:
            return self.channels[name]
        except KeyError as exc:
            raise KeyError(
                f"Loss channel {name!r} not in materials DB {self.name!r}; "
                f"have {sorted(self.channels)}"
            ) from exc


def load_materials_db(path: str | Path) -> MaterialsDB:
    """Parse a materials-DB YAML/JSON file. Raises on any schema violation."""
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return MaterialsDB.model_validate(data)


def illustrative_silicon_db() -> MaterialsDB:
    """Order-of-magnitude loss database for Nb/Al on high-resistivity silicon.

    NOT calibrated to any foundry. Loaded from
    ``knowledge/materials/illustrative_si_surface_loss.yaml`` so the same
    values are reachable from disk (e.g. for a foundry to fork the file) and
    from this convenience function. Values are typical of the published
    literature and exist so the coherence *machinery* can run and be tested;
    swap in measured values via the measurement-calibration loop before
    trusting any absolute T1 number.
    """
    return load_materials_db(MATERIALS_DIR / "illustrative_si_surface_loss.yaml")
