"""Quantum Device Dataset — open format for device data sharing.

Supports:
    - Open device dataset format (JSON Lines + Parquet)
    - Device metadata standard
    - GDS hash / process hash / measurement hash tracking
    - HuggingFace dataset export
    - Device similarity search (cosine on geometry embeddings)
    - Failed-device database
    - Negative training examples
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np



# ---------------------------------------------------------------------------
# Dataset schema
# ---------------------------------------------------------------------------

@dataclass
class DeviceMetadata:
    """Standard device metadata following the open format."""
    device_id: str = ""
    device_type: str = ""                    # LJPA, transmon, SQUID, CPW, resonator
    topology: str = ""                       # lumped, distributed, coplanar, microstrip
    version: str = "1.0.0"
    license: str = "MIT"
    created_by: str = "text-to-gds"
    created_at: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    references: list[str] = field(default_factory=list)  # DOIs, arXiv IDs


@dataclass
class GeometryData:
    """Geometry features for ML."""
    device_type: str = ""
    parameters: dict[str, float] = field(default_factory=dict)
    layer_count: int = 0
    port_count: int = 0
    bbox_width_um: float = 0.0
    bbox_height_um: float = 0.0
    total_area_um2: float = 0.0
    gds_hash: str = ""                       # SHA-256 of GDS bytes
    embedding: list[float] = field(default_factory=list)  # from layout transformer


@dataclass
class ProcessData:
    """Fabrication process data."""
    process_id: str = ""
    process_hash: str = ""                   # hash of the PDK YAML
    materials: list[str] = field(default_factory=list)
    layer_stack: list[dict[str, Any]] = field(default_factory=list)
    min_feature_um: float = 0.0
    jc_ua_per_um2: float = 0.0
    tc_k: float = 0.0


@dataclass
class SimulationData:
    """Simulation results."""
    engine: str = ""                         # hfss, openEMS, palace, ...
    frequency_ghz: float = 0.0
    s_parameters: list[complex] = field(default_factory=list)
    s_frequency_points: int = 0
    quality_factor: float = 0.0
    impedance_ohm: float = 0.0
    effective_permittivity: float = 0.0
    gain_db: float = 0.0
    bandwidth_mhz: float = 0.0
    noise_temperature_k: float = 0.0
    p1db_dbm: float = 0.0
    convergence: bool = True
    mesh_elements: int = 0
    solver_time_s: float = 0.0


@dataclass
class MeasurementData:
    """Measured device data."""
    measurement_hash: str = ""
    temperature_k: float = 0.0
    magnetic_field_t: float = 0.0
    pump_frequency_ghz: float = 0.0
    pump_power_dbm: float = 0.0
    gain_db: float = 0.0
    bandwidth_mhz: float = 0.0
    noise_temperature_k: float = 0.0
    p1db_dbm: float = 0.0
    qi: float = 0.0
    qc: float = 0.0
    data_file: str = ""                      # path to raw data
    data_format: str = ""                    # csv, json, hdf5


@dataclass
class DeviceRecord:
    """Complete device record in open dataset format."""
    metadata: DeviceMetadata = field(default_factory=DeviceMetadata)
    geometry: GeometryData = field(default_factory=GeometryData)
    process: ProcessData = field(default_factory=ProcessData)
    simulations: list[SimulationData] = field(default_factory=list)
    measurements: list[MeasurementData] = field(default_factory=list)
    quality_score: float = 0.0
    is_negative_example: bool = False        # failed device for training
    failure_reason: str = ""
    reproducibility_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": asdict(self.metadata),
            "geometry": asdict(self.geometry),
            "process": asdict(self.process),
            "simulations": [asdict(s) for s in self.simulations],
            "measurements": [asdict(m) for m in self.measurements],
            "quality_score": self.quality_score,
            "is_negative_example": self.is_negative_example,
            "failure_reason": self.failure_reason,
            "reproducibility_score": self.reproducibility_score,
        }

    def compute_hashes(self, gds_path: str | Path | None = None) -> None:
        """Compute content hashes for dedup and versioning."""
        if gds_path:
            self.geometry.gds_hash = hashlib.sha256(
                Path(gds_path).read_bytes()
            ).hexdigest()


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class QuantumDeviceDataset:
    """Open dataset for quantum devices.

    Format: JSONL (one device per line) with metadata header.
    Supports HuggingFace datasets export.

    Usage::

        ds = QuantumDeviceDataset("workspace/dataset")
        ds.add_device(record)
        ds.export_huggingface("workspace/hf_dataset")
        similar = ds.find_similar(target_geometry_embedding)
    """

    def __init__(self, root: str | Path = "workspace/dataset"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._devices_path = self.root / "devices.jsonl"
        self._devices: list[DeviceRecord] = []
        self._load()

    def _load(self) -> None:
        if self._devices_path.exists():
            for line in self._devices_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        rec = DeviceRecord(
                            metadata=DeviceMetadata(**data.get("metadata", {})),
                            geometry=GeometryData(**data.get("geometry", {})),
                            process=ProcessData(**data.get("process", {})),
                            simulations=[SimulationData(**s) for s in data.get("simulations", [])],
                            measurements=[MeasurementData(**m) for m in data.get("measurements", [])],
                            quality_score=data.get("quality_score", 0.0),
                            is_negative_example=data.get("is_negative_example", False),
                            failure_reason=data.get("failure_reason", ""),
                            reproducibility_score=data.get("reproducibility_score", 0.0),
                        )
                        self._devices.append(rec)
                    except (json.JSONDecodeError, TypeError):
                        pass

    def add_device(self, record: DeviceRecord) -> str:
        """Add a device to the dataset. Returns device_id."""
        self._devices.append(record)
        with open(self._devices_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), default=str) + "\n")
        return record.metadata.device_id

    def add_negative_example(
        self,
        record: DeviceRecord,
        reason: str = "",
    ) -> str:
        """Add a failed device as a negative training example."""
        record.is_negative_example = True
        record.failure_reason = reason
        return self.add_device(record)

    def get_device(self, device_id: str) -> DeviceRecord | None:
        for rec in self._devices:
            if rec.metadata.device_id == device_id:
                return rec
        return None

    def query(
        self,
        device_type: str | None = None,
        process_id: str | None = None,
        tags: list[str] | None = None,
        include_negatives: bool = False,
        limit: int = 100,
    ) -> list[DeviceRecord]:
        """Query devices with optional filters."""
        results: list[DeviceRecord] = []
        for rec in self._devices:
            if not include_negatives and rec.is_negative_example:
                continue
            if device_type and rec.metadata.device_type != device_type:
                continue
            if process_id and rec.process.process_id != process_id:
                continue
            if tags and not any(t in rec.metadata.tags for t in tags):
                continue
            results.append(rec)
            if len(results) >= limit:
                break
        return results

    def count(self, include_negatives: bool = False) -> int:
        if include_negatives:
            return len(self._devices)
        return sum(1 for r in self._devices if not r.is_negative_example)

    # -- similarity search ----------------------------------------------------

    def find_similar(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Find devices with similar geometry embeddings (cosine similarity)."""
        if not embedding:
            return []

        target = np.array(embedding, dtype=np.float64)
        target_norm = np.linalg.norm(target)
        if target_norm == 0:
            return []

        scores: list[tuple[float, DeviceRecord]] = []
        for rec in self._devices:
            if not rec.geometry.embedding:
                continue
            dev_emb = np.array(rec.geometry.embedding, dtype=np.float64)
            dev_norm = np.linalg.norm(dev_emb)
            if dev_norm == 0:
                continue
            cosine = float(np.dot(target, dev_emb) / (target_norm * dev_norm))
            scores.append((cosine, rec))

        scores.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "device_id": rec.metadata.device_id,
                "device_type": rec.metadata.device_type,
                "similarity": round(score, 4),
                "process_id": rec.process.process_id,
            }
            for score, rec in scores[:top_k]
        ]

    # -- HuggingFace export ---------------------------------------------------

    def export_huggingface(self, output_dir: str | Path) -> dict[str, Any]:
        """Export dataset in HuggingFace datasets format.

        Creates:
            dataset_dict.json
            data/train-00000-of-00001.parquet (or jsonl)
            dataset_info.json
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        records = []
        for rec in self._devices:
            records.append({
                "device_id": rec.metadata.device_id,
                "device_type": rec.metadata.device_type,
                "topology": rec.metadata.topology,
                "tags": json.dumps(rec.metadata.tags),
                "geometry_params": json.dumps(rec.geometry.parameters),
                "gds_hash": rec.geometry.gds_hash,
                "process_id": rec.process.process_id,
                "process_hash": rec.process.process_hash,
                "simulation_engine": (
                    rec.simulations[0].engine if rec.simulations else ""
                ),
                "frequency_ghz": (
                    rec.simulations[0].frequency_ghz if rec.simulations else 0.0
                ),
                "gain_db": (
                    rec.simulations[0].gain_db if rec.simulations else 0.0
                ),
                "quality_factor": (
                    rec.simulations[0].quality_factor if rec.simulations else 0.0
                ),
                "impedance_ohm": (
                    rec.simulations[0].impedance_ohm if rec.simulations else 0.0
                ),
                "is_negative": rec.is_negative_example,
                "failure_reason": rec.failure_reason,
                "quality_score": rec.quality_score,
            })

        # Write JSONL
        jsonl_path = out / "data.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

        # Write dataset info
        info = {
            "description": "Quantum Device Dataset from Text-to-GDS",
            "version": "1.0.0",
            "features": {k: type(v).__name__ for k, v in records[0].items()} if records else {},
            "num_examples": len(records),
            "license": "MIT",
            "source": "https://github.com/JungluChen/Text-to-Layout",
        }
        (out / "dataset_info.json").write_text(
            json.dumps(info, indent=2), encoding="utf-8"
        )

        # Write HF metadata
        hf_meta = {
            "data": [{"key": "data.jsonl", "filename": "data.jsonl"}],
        }
        (out / "dataset_dict.json").write_text(
            json.dumps(hf_meta, indent=2), encoding="utf-8"
        )

        return {
            "status": "exported",
            "output_dir": str(out),
            "num_records": len(records),
            "files": ["data.jsonl", "dataset_info.json", "dataset_dict.json"],
        }

    # -- statistics -----------------------------------------------------------

    def statistics(self) -> dict[str, Any]:
        """Dataset statistics."""
        total = len(self._devices)
        negatives = sum(1 for r in self._devices if r.is_negative_example)
        types: dict[str, int] = {}
        processes: dict[str, int] = {}
        for rec in self._devices:
            t = rec.metadata.device_type or "unknown"
            types[t] = types.get(t, 0) + 1
            p = rec.process.process_id or "unknown"
            processes[p] = processes.get(p, 0) + 1

        return {
            "total_devices": total,
            "positive_examples": total - negatives,
            "negative_examples": negatives,
            "device_types": types,
            "processes": processes,
            "dataset_path": str(self._devices_path),
        }
