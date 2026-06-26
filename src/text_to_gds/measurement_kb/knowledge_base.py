"""Measurement Knowledge Base for storing measurement data.

This module stores measurement data from quantum devices and provides
analysis capabilities for comparing measurements with simulations.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from text_to_gds.measurement_kb.types import (
    MeasurementRecord,
    MeasurementType,
    MeasurementAnalysis,
)


class MeasurementKnowledgeBase:
    """Stores and analyzes measurement data for quantum devices.
    
    The measurement knowledge base maintains a database of all measurements
    with their analysis results. It supports comparison between measurements
    and simulations, and provides statistical analysis of device performance.
    """
    
    def __init__(self, database_path: str | Path | None = None) -> None:
        """Initialize the measurement knowledge base.
        
        Args:
            database_path: Path to the measurement database directory.
                If None, uses a default location.
        """
        if database_path is None:
            database_path = Path("measurement_database")
        
        self._db_path = Path(database_path)
        self._db_path.mkdir(parents=True, exist_ok=True)
        
        self._records: dict[str, MeasurementRecord] = {}
        self._analyses: dict[str, list[MeasurementAnalysis]] = {}
        self._load_database()
    
    def store(self, record: MeasurementRecord) -> None:
        """Store a measurement record in the database.
        
        Args:
            record: The measurement record to store.
        """
        self._records[record.id] = record
        self._save_record(record)
    
    def retrieve(self, record_id: str) -> MeasurementRecord | None:
        """Retrieve a measurement record by ID.
        
        Args:
            record_id: The ID of the measurement record to retrieve.
            
        Returns:
            The measurement record if found, None otherwise.
        """
        return self._records.get(record_id)
    
    def search(
        self,
        design_id: str | None = None,
        measurement_type: MeasurementType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[MeasurementRecord]:
        """Search for measurement records.
        
        Args:
            design_id: Filter by design ID.
            measurement_type: Filter by measurement type.
            start_time: Filter by start time.
            end_time: Filter by end time.
            
        Returns:
            List of matching measurement records.
        """
        results = []
        
        for record in self._records.values():
            if design_id and record.design_id != design_id:
                continue
            
            if measurement_type and record.measurement_type != measurement_type:
                continue
            
            if start_time and record.timestamp < start_time:
                continue
            
            if end_time and record.timestamp > end_time:
                continue
            
            results.append(record)
        
        return results
    
    def analyze(
        self,
        record_id: str,
        analysis_type: str,
    ) -> MeasurementAnalysis:
        """Perform analysis on a measurement record.
        
        Args:
            record_id: ID of the measurement record to analyze.
            analysis_type: Type of analysis to perform.
            
        Returns:
            Analysis results.
        """
        record = self._records.get(record_id)
        if not record:
            return MeasurementAnalysis(
                measurement_id=record_id,
                analysis_type=analysis_type,
                results={"error": "Record not found"},
                confidence=0.0,
                warnings=["Record not found in database"],
            )
        
        # Perform analysis based on type
        if analysis_type == "extract_parameters":
            return self._extract_parameters(record)
        elif analysis_type == "compare_with_simulation":
            return self._compare_with_simulation(record)
        elif analysis_type == "statistical_analysis":
            return self._statistical_analysis(record)
        else:
            return MeasurementAnalysis(
                measurement_id=record_id,
                analysis_type=analysis_type,
                results={"error": f"Unknown analysis type: {analysis_type}"},
                confidence=0.0,
                warnings=[f"Unknown analysis type: {analysis_type}"],
            )
    
    def get_statistics(
        self,
        design_id: str,
        measurement_type: MeasurementType | None = None,
    ) -> dict[str, Any]:
        """Get statistical analysis of measurements for a design.
        
        Args:
            design_id: ID of the design.
            measurement_type: Optional filter by measurement type.
            
        Returns:
            Statistical analysis results.
        """
        records = self.search(design_id, measurement_type)
        
        if not records:
            return {"status": "no_measurements"}
        
        # Aggregate extracted parameters
        param_stats: dict[str, dict[str, float]] = {}
        for record in records:
            for param, value in record.extracted_params.items():
                if isinstance(value, (int, float)):
                    if param not in param_stats:
                        param_stats[param] = {"values": [], "count": 0}
                    param_stats[param]["values"].append(value)
                    param_stats[param]["count"] += 1
        
        # Compute statistics
        statistics: dict[str, Any] = {
            "design_id": design_id,
            "measurement_count": len(records),
            "parameters": {},
        }
        
        for param, stats in param_stats.items():
            values = stats["values"]
            statistics["parameters"][param] = {
                "count": len(values),
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "std": self._compute_std(values),
            }
        
        return statistics
    
    def compare_designs(
        self,
        design_ids: list[str],
        measurement_type: MeasurementType,
    ) -> dict[str, Any]:
        """Compare measurements across multiple designs.
        
        Args:
            design_ids: List of design IDs to compare.
            measurement_type: Type of measurement to compare.
            
        Returns:
            Comparison results.
        """
        comparisons: dict[str, Any] = {}
        
        for design_id in design_ids:
            records = self.search(design_id, measurement_type)
            if records:
                # Use the most recent record
                latest = max(records, key=lambda r: r.timestamp)
                comparisons[design_id] = {
                    "latest_measurement": latest.timestamp.isoformat(),
                    "extracted_params": latest.extracted_params,
                    "measurement_count": len(records),
                }
        
        return comparisons
    
    def _extract_parameters(
        self,
        record: MeasurementRecord,
    ) -> MeasurementAnalysis:
        """Extract parameters from measurement data."""
        extracted = {}
        warnings = []
        
        if record.measurement_type == MeasurementType.RESONATOR_SPECTRUM:
            # Extract resonance frequency and Q factor
            data = record.data
            if "frequency" in data and "s21" in data:
                freq = data["frequency"]
                s21 = data["s21"]
                
                # Find resonance (minimum of S21)
                if len(freq) > 0 and len(s21) > 0:
                    min_idx = min(range(len(s21)), key=lambda i: abs(s21[i]))
                    extracted["f0"] = freq[min_idx]
                    
                    # Estimate Q factor from 3dB bandwidth
                    # This is a simplified estimate
                    extracted["Q_estimated"] = freq[min_idx] / (freq[-1] - freq[0]) * len(freq)
        
        elif record.measurement_type == MeasurementType.S_PARAMETERS:
            # Extract S-parameter data
            data = record.data
            if "frequency" in data:
                extracted["frequency_range"] = [min(data["frequency"]), max(data["frequency"])]
        
        confidence = 0.8 if extracted else 0.3
        
        return MeasurementAnalysis(
            measurement_id=record.id,
            analysis_type="extract_parameters",
            results=extracted,
            confidence=confidence,
            warnings=warnings,
        )
    
    def _compare_with_simulation(
        self,
        record: MeasurementRecord,
    ) -> MeasurementAnalysis:
        """Compare measurement with simulation results."""
        # This would compare with solver results from the design
        return MeasurementAnalysis(
            measurement_id=record.id,
            analysis_type="compare_with_simulation",
            results={"status": "not_implemented"},
            confidence=0.0,
            warnings=["Simulation comparison not yet implemented"],
        )
    
    def _statistical_analysis(
        self,
        record: MeasurementRecord,
    ) -> MeasurementAnalysis:
        """Perform statistical analysis on measurement data."""
        return MeasurementAnalysis(
            measurement_id=record.id,
            analysis_type="statistical_analysis",
            results={"status": "not_implemented"},
            confidence=0.0,
            warnings=["Statistical analysis not yet implemented"],
        )
    
    def _compute_std(self, values: list[float]) -> float:
        """Compute standard deviation of values."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    def _load_database(self) -> None:
        """Load all measurement records from the database directory."""
        for record_file in self._db_path.glob("*.json"):
            try:
                with open(record_file, "r") as f:
                    data = json.load(f)
                record = MeasurementRecord.from_dict(data)
                self._records[record.id] = record
            except (json.JSONDecodeError, KeyError):
                continue
    
    def _save_record(self, record: MeasurementRecord) -> None:
        """Save a measurement record to the database directory."""
        record_file = self._db_path / f"{record.id}.json"
        with open(record_file, "w") as f:
            json.dump(record.to_dict(), f, indent=2)
