"""Quantum Device Database — SQLite-backed design memory.

Every device record stores layout, geometry, simulation, measurement,
fabrication, and provenance fields.  The database is the missing data
foundation that turns a layout generator into a learning system.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GeometryRecord:
    """Physical geometry of a quantum device."""
    device_type: str = ""                    # LJPA, transmon, SQUID, CPW, …
    topology: str = ""                       # coplanar, microstrip, lumped
    idc_fingers: int = 0
    idc_finger_width_um: float = 0.0
    idc_finger_length_um: float = 0.0
    idc_gap_um: float = 0.0
    squid_loop_area_um2: float = 0.0
    junction_area_um2: float = 0.0
    cpw_width_um: float = 0.0
    cpw_gap_um: float = 0.0
    cpw_length_um: float = 0.0
    resonator_length_um: float = 0.0
    coupling_capacitance_fF: float = 0.0
    shunt_capacitance_fF: float = 0.0
    via_diameter_um: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationRecord:
    """Electromagnetic and circuit simulation results."""
    engine: str = ""                         # hfss, openEMS, palace, elmer, …
    frequency_ghz: float = 0.0
    quality_factor: float = 0.0
    impedance_ohm: float = 0.0
    effective_permittivity: float = 0.0
    s11_db: float = 0.0
    s21_db: float = 0.0
    coupling_db: float = 0.0
    participation: float = 0.0
    bandwidth_mhz: float = 0.0
    gain_db: float = 0.0
    noise_temperature_k: float = 0.0
    p1db_dbm: float = 0.0
    critical_current_ua: float = 0.0
    josephson_inductance_ph: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeasurementRecord:
    """Measured performance from cryogenic or room-temperature tests."""
    gain_db: float = 0.0
    bandwidth_mhz: float = 0.0
    noise_temperature_k: float = 0.0
    p1db_dbm: float = 0.0
    saturation_power_dbm: float = 0.0
    pump_frequency_ghz: float = 0.0
    pump_power_dbm: float = 0.0
    flux_bias_ua: float = 0.0
    qi: float = 0.0
    qc: float = 0.0
    frequency_ghz: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FabricationRecord:
    """Fabrication process data."""
    process_id: str = ""                     # ncu_alox_2026, mit_ll_sfq, …
    oxidation_time_s: float = 0.0
    oxidation_temperature_k: float = 0.0
    jc_ua_per_um2: float = 0.0
    rs_ohm: float = 0.0
    tc_k: float = 0.0
    thickness_nm: float = 0.0
    sem_junction_width_nm: float = 0.0
    sem_junction_area_um2: float = 0.0
    yield_percent: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvenanceRecord:
    """Source references and lineage."""
    paper_doi: str = ""
    paper_title: str = ""
    paper_authors: str = ""
    paper_year: int = 0
    design_source: str = ""                  # "agent", "manual", "imported"
    parent_device_id: str = ""               # lineage for iterative designs
    notes: str = ""


@dataclass
class DeviceRecord:
    """Full device record — the atomic unit of the quantum device database."""
    device_id: str = ""
    gds_path: str = ""
    gds_hash: str = ""                       # SHA-256 of the GDS file bytes
    created_at: str = ""
    updated_at: str = ""
    status: str = "draft"                    # draft, simulated, measured, archived
    geometry: GeometryRecord = field(default_factory=GeometryRecord)
    simulations: list[SimulationRecord] = field(default_factory=list)
    measurements: list[MeasurementRecord] = field(default_factory=list)
    fabrication: FabricationRecord = field(default_factory=FabricationRecord)
    provenance: ProvenanceRecord = field(default_factory=ProvenanceRecord)
    tags: list[str] = field(default_factory=list)
    sidecar_json: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id       TEXT PRIMARY KEY,
    gds_path        TEXT,
    gds_hash        TEXT,
    created_at      TEXT,
    updated_at      TEXT,
    status          TEXT DEFAULT 'draft',
    tags            TEXT,
    sidecar_json    TEXT,
    geometry_json   TEXT,
    provenance_json TEXT,
    fabrication_json TEXT
);

CREATE TABLE IF NOT EXISTS simulations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT REFERENCES devices(device_id),
    engine          TEXT,
    data_json       TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS measurements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT REFERENCES devices(device_id),
    data_json       TEXT,
    created_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_sim_device ON simulations(device_id);
CREATE INDEX IF NOT EXISTS idx_meas_device ON measurements(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_id);
"""


class QuantumDeviceDatabase:
    """SQLite-backed store for quantum device design records.

    Usage::

        db = QuantumDeviceDatabase("workspace/devices.db")
        db.record_device(record)
        devices = db.query_devices(device_type="LJPA", status="measured")
    """

    def __init__(self, db_path: str | Path = "workspace/devices.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- write ---------------------------------------------------------------

    def record_device(self, record: DeviceRecord) -> str:
        """Insert or replace a full device record.  Returns *device_id*."""
        now = datetime.now(timezone.utc).isoformat()
        record.created_at = record.created_at or now
        record.updated_at = now

        self.conn.execute(
            """INSERT OR REPLACE INTO devices
               (device_id, gds_path, gds_hash, created_at, updated_at,
                status, tags, sidecar_json, geometry_json,
                provenance_json, fabrication_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record.device_id,
                record.gds_path,
                record.gds_hash,
                record.created_at,
                record.updated_at,
                record.status,
                json.dumps(record.tags),
                json.dumps(record.sidecar_json),
                json.dumps(asdict(record.geometry)),
                json.dumps(asdict(record.provenance)),
                json.dumps(asdict(record.fabrication)),
            ),
        )

        for sim in record.simulations:
            self._add_simulation(record.device_id, sim)
        for meas in record.measurements:
            self._add_measurement(record.device_id, meas)

        self.conn.commit()
        return record.device_id

    def _add_simulation(self, device_id: str, sim: SimulationRecord) -> int:
        cur = self.conn.execute(
            "INSERT INTO simulations (device_id, engine, data_json, created_at) VALUES (?,?,?,?)",
            (device_id, sim.engine, json.dumps(asdict(sim)),
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid or 0

    def _add_measurement(self, device_id: str, meas: MeasurementRecord) -> int:
        cur = self.conn.execute(
            "INSERT INTO measurements (device_id, data_json, created_at) VALUES (?,?,?)",
            (device_id, json.dumps(asdict(meas)),
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid or 0

    def add_simulation(self, device_id: str, sim: SimulationRecord) -> int:
        """Append a simulation result to an existing device."""
        return self._add_simulation(device_id, sim)

    def add_measurement(self, device_id: str, meas: MeasurementRecord) -> int:
        """Append a measurement result to an existing device."""
        return self._add_measurement(device_id, meas)

    # -- read ----------------------------------------------------------------

    def get_device(self, device_id: str) -> DeviceRecord | None:
        """Fetch a full device record with all child rows."""
        row = self.conn.execute(
            "SELECT * FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def query_devices(
        self,
        device_type: str | None = None,
        status: str | None = None,
        process_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
    ) -> list[DeviceRecord]:
        """Query devices with optional filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if status:
            clauses.append("status = ?")
            params.append(status)
        if process_id:
            clauses.append("fabrication_json LIKE ?")
            params.append(f'%"{process_id}"%')
        if device_type:
            clauses.append("geometry_json LIKE ?")
            params.append(f'%"device_type": "{device_type}"%')

        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)

        rows = self.conn.execute(
            f"SELECT * FROM devices{where} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()

        return [self._row_to_record(r) for r in rows]

    def list_all_device_ids(self) -> list[str]:
        """Return all device IDs."""
        rows = self.conn.execute("SELECT device_id FROM devices").fetchall()
        return [r["device_id"] for r in rows]

    def count_devices(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]

    def count_simulations(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM simulations").fetchone()[0]

    def count_measurements(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]

    def get_simulations(self, device_id: str) -> list[SimulationRecord]:
        rows = self.conn.execute(
            "SELECT data_json FROM simulations WHERE device_id = ? ORDER BY created_at",
            (device_id,),
        ).fetchall()
        return [SimulationRecord(**json.loads(r["data_json"])) for r in rows]

    def get_measurements(self, device_id: str) -> list[MeasurementRecord]:
        rows = self.conn.execute(
            "SELECT data_json FROM measurements WHERE device_id = ? ORDER BY created_at",
            (device_id,),
        ).fetchall()
        return [MeasurementRecord(**json.loads(r["data_json"])) for r in rows]

    # -- compute -------------------------------------------------------------

    def compute_gds_hash(self, gds_path: str | Path) -> str:
        """SHA-256 of a GDS file for dedup and versioning."""
        return hashlib.sha256(Path(gds_path).read_bytes()).hexdigest()

    def summary(self) -> dict[str, Any]:
        """Return database statistics."""
        return {
            "total_devices": self.count_devices(),
            "total_simulations": self.count_simulations(),
            "total_measurements": self.count_measurements(),
            "db_path": str(self.db_path),
        }

    # -- internal ------------------------------------------------------------

    def _row_to_record(self, row: sqlite3.Row) -> DeviceRecord:
        geo = GeometryRecord(**json.loads(row["geometry_json"] or "{}"))
        prov = ProvenanceRecord(**json.loads(row["provenance_json"] or "{}"))
        fab = FabricationRecord(**json.loads(row["fabrication_json"] or "{}"))
        sims = self.get_simulations(row["device_id"])
        meass = self.get_measurements(row["device_id"])
        return DeviceRecord(
            device_id=row["device_id"],
            gds_path=row["gds_path"] or "",
            gds_hash=row["gds_hash"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            status=row["status"] or "draft",
            geometry=geo,
            simulations=sims,
            measurements=meass,
            fabrication=fab,
            provenance=prov,
            tags=json.loads(row["tags"] or "[]"),
            sidecar_json=json.loads(row["sidecar_json"] or "{}"),
        )

    # -- export ---------------------------------------------------------------

    def export_training_pairs(self) -> list[dict[str, Any]]:
        """Export (layout_embedding, performance) pairs for ML training.

        Each pair contains geometry features and target simulation/measurement
        values.  Returns a list of dictionaries ready for DataLoader consumption.
        """
        devices = self.query_devices(limit=10_000)
        pairs: list[dict[str, Any]] = []
        for dev in devices:
            if not dev.simulations and not dev.measurements:
                continue
            geo = asdict(dev.geometry)
            targets: dict[str, Any] = {}
            if dev.simulations:
                best = max(dev.simulations, key=lambda s: s.frequency_ghz or 0)
                targets = {k: v for k, v in asdict(best).items() if v and k != "extra"}
            if dev.measurements:
                meas = asdict(dev.measurements[-1])
                targets["measured"] = {k: v for k, v in meas.items() if v and k != "extra"}
            pairs.append({
                "device_id": dev.device_id,
                "geometry": geo,
                "targets": targets,
                "tags": dev.tags,
            })
        return pairs
