"""Digital Twin engine — accumulates all engineering knowledge for a design.

Every design gets a twin that stores:
  Geometry → Physics → Simulation → Measurement → History → Packaging →
  Fabrication → Current Version → Expected Yield → Expected Frequency Drift →
  Expected Failure

The twin is the authoritative record for a design; it outlives any single run
and provides the foundation for comparing simulation vs measurement.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from text_to_gds.digital_twin.types import (
    DesignIteration,
    DigitalTwin,
    FabricationMetadata,
    GeometrySnapshot,
    MeasurementRecord,
    PhysicsState,
    ReliabilityPrediction,
    SimulationRun,
)


class DigitalTwinEngine:
    """Creates, updates, queries, and persists digital twins.

    Usage pattern:
        engine = DigitalTwinEngine(database_path="twins/")
        twin_id = engine.create_twin(name="JPA_v3", device_type="lumped_jpa")
        engine.record_geometry(twin_id, gds_path="...", sidecar_path="...")
        engine.record_simulation(twin_id, solver="JosephsonCircuits.jl", ...)
        engine.record_measurement(twin_id, measurement_type="gain_db", ...)
        report = engine.generate_report(twin_id)
    """

    def __init__(self, database_path: str | Path | None = None) -> None:
        if database_path is None:
            database_path = Path("digital_twins")
        self._db = Path(database_path)
        self._db.mkdir(parents=True, exist_ok=True)
        self._twins: dict[str, DigitalTwin] = {}
        self._load_all()

    # ─── Creation ─────────────────────────────────────────────────────────────

    def create_twin(
        self,
        name: str,
        device_type: str = "unknown",
        description: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Create a new digital twin. Returns twin_id."""
        import datetime
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        twin = DigitalTwin(
            name=name,
            device_type=device_type,
            description=description,
            created_at=now,
            updated_at=now,
            tags=tags or [],
        )
        self._twins[twin.id] = twin
        self._save(twin)
        return twin.id

    # ─── Recording ────────────────────────────────────────────────────────────

    def record_geometry(
        self,
        twin_id: str,
        *,
        gds_path: str,
        sidecar_path: str | None = None,
        layer_stack: dict[str, Any] | None = None,
        critical_dimensions: dict[str, float] | None = None,
        bounding_box_um: list[float] | None = None,
        total_area_um2: float = 0.0,
    ) -> None:
        twin = self._get(twin_id)
        twin.current_geometry = GeometrySnapshot(
            gds_path=gds_path,
            sidecar_path=sidecar_path,
            layer_stack=layer_stack or {},
            critical_dimensions=critical_dimensions or {},
            bounding_box_um=bounding_box_um or [],
            total_area_um2=total_area_um2,
        )
        self._touch(twin)

    def record_physics(
        self,
        twin_id: str,
        *,
        analytical: dict[str, Any] | None = None,
        extracted: dict[str, Any] | None = None,
        simulated: dict[str, Any] | None = None,
        measured: dict[str, Any] | None = None,
    ) -> None:
        twin = self._get(twin_id)
        if twin.current_physics is None:
            twin.current_physics = PhysicsState()
        ps = twin.current_physics
        if analytical:
            ps.analytical.update(analytical)
        if extracted:
            ps.extracted.update(extracted)
        if simulated:
            ps.simulated.update(simulated)
        if measured:
            ps.measured.update(measured)

        # Determine dominant source
        n_measured = len(ps.measured)
        n_simulated = len(ps.simulated)
        n_extracted = len(ps.extracted)
        n_analytical = len(ps.analytical)
        total = n_measured + n_simulated + n_extracted + n_analytical
        if total == 0:
            ps.dominant_source = "none"
            ps.confidence = 0.0
        elif n_measured >= n_simulated:
            ps.dominant_source = "measured"
            ps.confidence = min(1.0, 0.5 + 0.5 * n_measured / max(total, 1))
        elif n_simulated >= n_extracted:
            ps.dominant_source = "simulated"
            ps.confidence = min(0.85, 0.4 + 0.45 * n_simulated / max(total, 1))
        elif n_extracted > 0:
            ps.dominant_source = "extracted"
            ps.confidence = 0.6
        else:
            ps.dominant_source = "analytical"
            ps.confidence = 0.5

        self._touch(twin)

    def record_simulation(
        self,
        twin_id: str,
        *,
        solver: str,
        status: str,
        results: dict[str, Any] | None = None,
        input_path: str | None = None,
        output_path: str | None = None,
        runtime_s: float = 0.0,
        solver_version: str = "",
        notes: str = "",
    ) -> None:
        import datetime
        twin = self._get(twin_id)
        run = SimulationRun(
            solver=solver,
            status=status,
            results=results or {},
            input_path=input_path,
            output_path=output_path,
            runtime_s=runtime_s,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            solver_version=solver_version,
            notes=notes,
        )
        twin.simulation_runs.append(run)
        self._touch(twin)

    def record_measurement(
        self,
        twin_id: str,
        *,
        measurement_type: str,
        value: float | None = None,
        unit: str = "",
        uncertainty: float | None = None,
        temperature_mk: float | None = None,
        setup: str = "",
        raw_data_path: str | None = None,
        notes: str = "",
    ) -> None:
        import datetime
        twin = self._get(twin_id)
        meas = MeasurementRecord(
            measurement_type=measurement_type,
            value=value,
            unit=unit,
            uncertainty=uncertainty,
            temperature_mk=temperature_mk,
            date=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            setup=setup,
            raw_data_path=raw_data_path,
            notes=notes,
        )
        twin.measurements.append(meas)
        self._touch(twin)

    def record_iteration(
        self,
        twin_id: str,
        *,
        description: str,
        changes: list[str] | None = None,
        committee_score: float = 0.0,
        approved: bool = False,
    ) -> None:
        import datetime
        twin = self._get(twin_id)
        n = len(twin.design_iterations) + 1
        iteration = DesignIteration(
            iteration=n,
            description=description,
            changes=changes or [],
            committee_score=committee_score,
            approved=approved,
            geometry_snapshot=twin.current_geometry,
            physics_state=twin.current_physics,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        )
        twin.design_iterations.append(iteration)
        twin.committee_score = committee_score
        self._touch(twin)

    def record_fabrication(
        self,
        twin_id: str,
        *,
        process: str = "",
        foundry: str = "",
        run_id: str = "",
        tapeout_date: str = "",
        expected_yield_pct: float | None = None,
        critical_current_density_ua_um2: float | None = None,
    ) -> None:
        twin = self._get(twin_id)
        twin.fabrication = FabricationMetadata(
            process=process,
            foundry=foundry,
            run_id=run_id,
            tapeout_date=tapeout_date,
            expected_yield_pct=expected_yield_pct,
            critical_current_density_ua_um2=critical_current_density_ua_um2,
        )
        self._touch(twin)

    # ─── Analysis ─────────────────────────────────────────────────────────────

    def predict_reliability(self, twin_id: str) -> ReliabilityPrediction:
        """Predict reliability from available physics and simulation data.

        Uses analytical models; solver evidence improves confidence.
        """
        twin = self._get(twin_id)
        phys = twin.current_physics or PhysicsState()

        freq_drift = None
        t1_us = None
        t2_us = None
        dominant_loss = "unknown"
        failure_modes = []
        confidence = 0.0
        method = "analytical"

        # Frequency drift: TLS noise typically ~1-10 MHz/year for superconducting circuits
        freq_drift = 2.0  # MHz/year baseline from literature
        failure_modes.append({
            "mode": "frequency_drift",
            "mechanism": "TLS fluctuations",
            "expected_scale": "1-10 MHz/year",
            "reference": "Müller et al., Rep. Prog. Phys. 82 124501 (2019)",
        })

        # T1 from Purcell if resonator data available
        res_freq = phys.best_value("resonator_frequency_ghz")
        q_factor = phys.best_value("quality_factor")
        if res_freq and q_factor:
            t1_us = float(q_factor) / (2 * math.pi * float(res_freq) * 1e9) * 1e6
            t1_us = min(t1_us, 1000.0)
            dominant_loss = "internal_Q"
            confidence = 0.6
            method = "extracted"
            failure_modes.append({
                "mode": "t1_loss",
                "mechanism": "Purcell + internal Q",
                "expected_t1_us": t1_us,
                "reference": "Koch et al., PRA 76 042319 (2007)",
            })

        # T2 ≈ 2*T1 for flux-insensitive transmons
        if t1_us is not None:
            t2_us = 1.5 * t1_us
            failure_modes.append({
                "mode": "dephasing",
                "mechanism": "1/f charge noise + flux noise",
                "expected_t2_us": t2_us,
                "reference": "Ithier et al., PRB 72 134519 (2005)",
            })

        # Check for simulation evidence to upgrade confidence
        for run in twin.simulation_runs:
            if run.status == "EXECUTED":
                confidence = min(confidence + 0.15, 1.0)
                method = "solver_assisted"

        twin.reliability = ReliabilityPrediction(
            expected_frequency_drift_mhz_per_year=freq_drift,
            expected_t1_us=t1_us,
            expected_t2_us=t2_us,
            dominant_loss_mechanism=dominant_loss,
            failure_modes=failure_modes,
            confidence=confidence,
            analysis_method=method,
        )
        self._touch(twin)
        return twin.reliability

    def compare_simulation_vs_measurement(
        self, twin_id: str
    ) -> dict[str, Any]:
        """Compare simulation results against physical measurements.

        Returns agreement analysis: which quantities agree, which diverge.
        """
        twin = self._get(twin_id)
        comparisons: list[dict[str, Any]] = []

        # Build measurement index by type
        meas_by_type: dict[str, list[MeasurementRecord]] = {}
        for m in twin.measurements:
            meas_by_type.setdefault(m.measurement_type, []).append(m)

        # Build simulation result index
        sim_results: dict[str, Any] = {}
        for run in twin.simulation_runs:
            if run.status == "EXECUTED":
                sim_results.update(run.results)

        # Compare each measured quantity
        for mtype, records in meas_by_type.items():
            measured_val = records[-1].value  # latest measurement
            simulated_val = sim_results.get(mtype)

            if measured_val is None or simulated_val is None:
                comparisons.append({
                    "quantity": mtype,
                    "measured": measured_val,
                    "simulated": simulated_val,
                    "agreement": "unknown",
                    "relative_error": None,
                })
                continue

            try:
                m, s = float(measured_val), float(simulated_val)
                if m != 0:
                    rel_err = abs(m - s) / abs(m)
                else:
                    rel_err = abs(s)
                agreement = (
                    "excellent" if rel_err < 0.02
                    else "good" if rel_err < 0.05
                    else "acceptable" if rel_err < 0.15
                    else "poor"
                )
                comparisons.append({
                    "quantity": mtype,
                    "measured": m,
                    "simulated": s,
                    "agreement": agreement,
                    "relative_error": rel_err,
                    "unit": records[-1].unit,
                })
            except (TypeError, ValueError):
                comparisons.append({
                    "quantity": mtype,
                    "measured": measured_val,
                    "simulated": simulated_val,
                    "agreement": "type_error",
                    "relative_error": None,
                })

        return {
            "schema": "text-to-gds.twin-comparison.v1",
            "twin_id": twin_id,
            "comparisons": comparisons,
            "total_compared": len(comparisons),
            "n_excellent": sum(1 for c in comparisons if c["agreement"] == "excellent"),
            "n_good": sum(1 for c in comparisons if c["agreement"] == "good"),
            "n_poor": sum(1 for c in comparisons if c["agreement"] == "poor"),
        }

    # ─── Report ───────────────────────────────────────────────────────────────

    def generate_report(self, twin_id: str) -> dict[str, Any]:
        """Generate a comprehensive engineering report for a digital twin."""
        twin = self._get(twin_id)

        # Summarize simulation coverage
        solver_status: dict[str, str] = {}
        for run in twin.simulation_runs:
            solver_status[run.solver] = run.status

        # Summarize measurement coverage
        meas_types = list({m.measurement_type for m in twin.measurements})

        # Best physics values
        best_physics: dict[str, Any] = {}
        if twin.current_physics:
            for key in (
                "frequency_ghz", "resonator_frequency_ghz", "quality_factor",
                "gain_db", "bandwidth_mhz", "impedance_ohm",
                "junction_inductance_nh", "critical_current_ua",
                "capacitance_ff", "coupling_g_mhz",
            ):
                val = twin.current_physics.best_value(key)
                if val is not None:
                    best_physics[key] = val

        return {
            "schema": "text-to-gds.twin-report.v1",
            "id": twin.id,
            "name": twin.name,
            "device_type": twin.device_type,
            "description": twin.description,
            "created_at": twin.created_at,
            "committee_score": twin.committee_score,
            "signoff_level": twin.signoff_level,
            "design_iterations": len(twin.design_iterations),
            "geometry": twin.current_geometry.to_dict() if twin.current_geometry else None,
            "best_physics": best_physics,
            "physics_dominant_source": twin.current_physics.dominant_source if twin.current_physics else "none",
            "solver_coverage": solver_status,
            "measurement_types": meas_types,
            "reliability": twin.reliability.to_dict() if twin.reliability else None,
            "fabrication": twin.fabrication.to_dict() if twin.fabrication else None,
            "literature_refs": twin.literature_refs,
            "tags": twin.tags,
            "notes": twin.notes,
        }

    # ─── Persistence ──────────────────────────────────────────────────────────

    def get(self, twin_id: str) -> DigitalTwin | None:
        return self._twins.get(twin_id)

    def list_twins(
        self,
        device_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[DigitalTwin]:
        result = list(self._twins.values())
        if device_type:
            result = [t for t in result if t.device_type == device_type]
        if tags:
            result = [t for t in result if all(tag in t.tags for tag in tags)]
        return result

    def _get(self, twin_id: str) -> DigitalTwin:
        twin = self._twins.get(twin_id)
        if twin is None:
            raise KeyError(f"Digital twin not found: {twin_id!r}")
        return twin

    def _touch(self, twin: DigitalTwin) -> None:
        import datetime
        twin.updated_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        self._save(twin)

    def _save(self, twin: DigitalTwin) -> None:
        path = self._db / f"{twin.id}.json"
        path.write_text(json.dumps(twin.to_dict(), indent=2, default=str), encoding="utf-8")

    def _load_all(self) -> None:
        for path in self._db.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("schema") == "text-to-gds.digital-twin.v1":
                    twin = DigitalTwin.from_dict(data)
                    self._twins[twin.id] = twin
            except (json.JSONDecodeError, KeyError):
                continue
