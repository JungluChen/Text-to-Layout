"""Feed PDK substrate properties and provenance into an EPR analysis.

Sprint 2/4 contract: an EPR report is never emitted without saying which PDK
its material assumptions came from. The bridge does two things:

- builds a :class:`MaterialsDB` whose *substrate* channel uses the PDK's own
  ``epsilon_r`` / ``loss_tangent`` (the thin-film interface channels stay on
  the literature scaling DB — a PDK YAML has no MS/SA/MA loss tangents until
  the measurement-calibration loop supplies them, and inventing them here
  would be fake physics);
- computes the byte-exact :class:`~textlayout.pdk.provenance.PDKProvenance`
  record (name, version, sha256 of the file, calibration status) that the
  resulting :class:`EPRResult` embeds.

Using a PDK never upgrades the honesty status: an analytical scaling model
stays ``EPR_ANALYTICAL_ONLY`` no matter how calibrated its inputs are.
"""

from __future__ import annotations

from pathlib import Path

from textlayout.epr.materials import MaterialsDB, illustrative_silicon_db
from textlayout.knowledge.technology_library import PDKS_DIR
from textlayout.pdk.loader import load_pdk
from textlayout.pdk.models import CALIBRATION_ILLUSTRATIVE
from textlayout.pdk.provenance import PDKProvenance, describe_pdk_file

DEFAULT_PDK_NAME = "generic_2metal"


def resolve_pdk_path(name_or_path: str) -> Path:
    """Accept a registered PDK name (``generic_2metal``) or an explicit path."""
    candidate = Path(name_or_path)
    if candidate.is_file():
        return candidate
    registered = PDKS_DIR / f"{name_or_path}.yaml"
    if registered.is_file():
        return registered
    available = sorted(p.stem for p in PDKS_DIR.glob("*.yaml"))
    raise FileNotFoundError(
        f"PDK {name_or_path!r} is neither a file nor a registered PDK name; "
        f"registered: {available}"
    )


def materials_db_from_pdk(pdk_path: str | Path) -> tuple[MaterialsDB, PDKProvenance]:
    """Materials DB with the PDK's substrate values + the PDK's provenance."""
    path = resolve_pdk_path(str(pdk_path))
    pdk = load_pdk(path)
    provenance = describe_pdk_file(path)

    base = illustrative_silicon_db()
    substrate = base.channel("substrate")
    channels = dict(base.channels)
    channels["substrate"] = substrate.model_copy(
        update={
            "material": pdk.substrate.material,
            "tan_delta": pdk.substrate.loss_tangent,
            "epsilon_r": pdk.substrate.epsilon_r,
            "calibration": (
                substrate.calibration
                if pdk.calibration_status == CALIBRATION_ILLUSTRATIVE
                else pdk.calibration_status
            ),
            "source": f"PDK {pdk.name} v{pdk.version} ({pdk.calibration_status})",
        }
    )
    db = base.model_copy(
        update={
            "name": f"{base.name}+pdk:{pdk.name}",
            "channels": channels,
            "notes": [
                *base.notes,
                f"Substrate channel overridden from PDK {pdk.name} v{pdk.version} "
                f"(calibration_status={pdk.calibration_status}); interface channels "
                "remain literature-scaled until measurement calibration supplies them.",
            ],
        }
    )
    return db, provenance
