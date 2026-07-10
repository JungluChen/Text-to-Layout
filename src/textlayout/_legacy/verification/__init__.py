"""GDS-derived verification entrypoints plus legacy verification API."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from textlayout._legacy.verification.connectivity import extract_connectivity
from textlayout._legacy.verification.drc import run_drc
from textlayout._legacy.verification.lvs import generate_lvs_report

_LEGACY_PATH = Path(__file__).resolve().parents[1] / "verification.py"
_legacy_spec = importlib.util.spec_from_file_location("_text_to_gds_legacy_verification", _LEGACY_PATH)
if _legacy_spec is None or _legacy_spec.loader is None:
    raise ImportError(f"Cannot load legacy verification module at {_LEGACY_PATH}")
_legacy = importlib.util.module_from_spec(_legacy_spec)
_legacy_spec.loader.exec_module(_legacy)

extract_equivalent_circuit = _legacy.extract_equivalent_circuit
extract_circuit_from_gds = _legacy.extract_circuit_from_gds
run_superconducting_lvs = _legacy.run_superconducting_lvs
generate_spice_netlist = _legacy.generate_spice_netlist
generate_josephsoncircuits_model = _legacy.generate_josephsoncircuits_model
design_fingerprint = _legacy.design_fingerprint
design_version_diff = _legacy.design_version_diff
initialize_device_version_store = _legacy.initialize_device_version_store
commit_device_version = _legacy.commit_device_version
device_version_history = _legacy.device_version_history
chip_version_diff = _legacy.chip_version_diff
gds_visual_diff = _legacy.gds_visual_diff
generate_wafer_mask = _legacy.generate_wafer_mask

__all__ = [
    "chip_version_diff",
    "commit_device_version",
    "design_fingerprint",
    "design_version_diff",
    "device_version_history",
    "extract_circuit_from_gds",
    "extract_connectivity",
    "extract_equivalent_circuit",
    "gds_visual_diff",
    "generate_josephsoncircuits_model",
    "generate_lvs_report",
    "generate_spice_netlist",
    "generate_wafer_mask",
    "initialize_device_version_store",
    "run_drc",
    "run_superconducting_lvs",
]
