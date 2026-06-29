"""Elmer FEM solver — electrostatic capacitance extraction.

Implements the five-stage EM solver interface for Elmer:
  prepare()  — write .sif (Solver Input File) and geometry mesh directives
  mesh()     — run ElmerGrid or gmsh to produce .msh
  solve()    — run ElmerSolver to compute C-matrix
  parse()    — extract C-matrix from result files
  validate() — check positive-definiteness and physical bounds

If ElmerSolver is not on PATH → status="SKIPPED".
NO ElmerSolver output file = NO simulation.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import time
from pathlib import Path

from text_to_gds.solvers.interface import (
    AvailabilityStatus,
    CapacitanceSolver,
    GeometrySpec,
    SolverOutput,
)

_SCHEMA = "text-to-gds.elmer-capacitance.v1"


class ElmerFEMSolver(CapacitanceSolver):
    """Electrostatic capacitance extraction via Elmer FEM."""

    def __init__(
        self,
        *,
        elmer_solver: str = "ElmerSolver",
        elmer_grid: str = "ElmerGrid",
        timeout_seconds: int = 1800,
    ) -> None:
        self._elmer = elmer_solver
        self._elmergrid = elmer_grid
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "ElmerFEM"

    def is_available(self) -> AvailabilityStatus:
        found = shutil.which(self._elmer)
        if found is None:
            return AvailabilityStatus(
                available=False,
                reason=(
                    "ElmerSolver not found on PATH. "
                    "Install from https://www.elmerfem.org/blog/binaries/ "
                    "and add to PATH."
                ),
            )
        try:
            result = subprocess.run(
                [self._elmer, "--version"],
                capture_output=True, text=True, timeout=15,
            )
            version = result.stdout.strip().splitlines()[0] if result.stdout else "unknown"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            version = "unknown"

        return AvailabilityStatus(
            available=True,
            reason="ElmerSolver found",
            version=version,
            executable=found,
        )

    def prepare(self, geometry: GeometrySpec, output_dir: Path) -> SolverOutput:
        """Write Elmer SIF for electrostatic C-matrix extraction."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        params = geometry.parameters
        device_type = geometry.device_type
        stack = geometry.process_stack

        # Build simple box geometry
        width_um = float(params.get("center_width_um", params.get("finger_width_um", 5.0)))
        gap_um = float(params.get("gap_um", params.get("finger_gap_um", 3.0)))
        length_um = float(params.get("length_um", params.get("overlap_length_um", 100.0)))
        eps_r = float(stack.get("dielectric_constant", 11.45))
        metal_thickness_nm = float(stack.get("metal_thickness_nm", 180.0))

        # Write geometry input for ElmerGrid (box model)
        geo_file = output_dir / "geometry.geo"
        geo_content = _build_geo(
            width_um=width_um,
            gap_um=gap_um,
            length_um=length_um,
            metal_thickness_nm=metal_thickness_nm,
            device_type=device_type,
        )
        geo_file.write_text(geo_content, encoding="utf-8")

        # Write SIF
        sif_file = output_dir / "capacitance.sif"
        sif_content = _build_sif(
            eps_r=eps_r,
            device_type=device_type,
        )
        sif_file.write_text(sif_content, encoding="utf-8")

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="SIF prepared",
            output_dir=output_dir,
            artifacts={"sif": sif_file, "geometry": geo_file},
            parsed_data={
                "device_type": device_type,
                "width_um": width_um,
                "gap_um": gap_um,
                "length_um": length_um,
                "eps_r": eps_r,
            },
        )

    def mesh(self, prepared: SolverOutput, output_dir: Path) -> SolverOutput:
        """Generate mesh using ElmerGrid or gmsh."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        geo_file = prepared.artifacts.get("geometry")
        if geo_file is None:
            return SolverOutput.failed(self.name, "No geometry file for meshing", output_dir)

        mesh_dir = output_dir / "mesh"
        mesh_dir.mkdir(exist_ok=True)

        elmergrid = shutil.which(self._elmergrid)
        if elmergrid is None:
            return SolverOutput.failed(
                self.name,
                "ElmerGrid not found; cannot mesh without it",
                output_dir,
            )

        try:
            result = subprocess.run(
                [elmergrid, "14", "2", str(geo_file), "-out", str(mesh_dir)],
                capture_output=True, text=True, timeout=300,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return SolverOutput.failed(self.name, f"ElmerGrid failed: {e}", output_dir)

        if result.returncode != 0:
            return SolverOutput.failed(
                self.name,
                f"ElmerGrid exited {result.returncode}: {result.stderr[-300:]}",
                output_dir,
            )

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="mesh generated",
            output_dir=output_dir,
            artifacts={**prepared.artifacts, "mesh_dir": mesh_dir},
            parsed_data=prepared.parsed_data,
        )

    def solve(self, meshed: SolverOutput, output_dir: Path) -> SolverOutput:
        """Run ElmerSolver."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        sif_file = meshed.artifacts.get("sif")
        if sif_file is None or not sif_file.exists():
            return SolverOutput.failed(self.name, "SIF file not found", output_dir)

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                [self._elmer, str(sif_file)],
                capture_output=True, text=True,
                timeout=self._timeout, cwd=str(output_dir),
            )
        except subprocess.TimeoutExpired:
            return SolverOutput.failed(
                self.name, f"ElmerSolver timed out after {self._timeout}s", output_dir
            )
        except FileNotFoundError:
            return SolverOutput.failed(self.name, "ElmerSolver not found", output_dir)

        elapsed = time.monotonic() - t0
        result_file = output_dir / "capacitance.dat"

        if result.returncode != 0 or not result_file.exists():
            return SolverOutput.failed(
                self.name,
                f"ElmerSolver exited {result.returncode}; no output file. "
                f"stderr: {result.stderr[-400:] if result.stderr else 'none'}",
                output_dir,
            )

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="ElmerSolver completed",
            output_dir=output_dir,
            artifacts={**meshed.artifacts, "capacitance_dat": result_file},
            parsed_data=meshed.parsed_data,
            execution_time_s=elapsed,
            version=avail.version,
        )

    def parse(self, solved: SolverOutput, output_dir: Path) -> SolverOutput:
        """Parse Elmer capacitance.dat output."""
        dat_file = solved.artifacts.get("capacitance_dat")
        if dat_file is None or not dat_file.exists():
            return SolverOutput.failed(
                self.name, "capacitance.dat not found — no solver result", output_dir
            )

        try:
            c_pf = _parse_elmer_capacitance(dat_file)
        except Exception as e:
            return SolverOutput.failed(self.name, f"Parse error: {e}", output_dir)

        result_json = output_dir / "elmer_result.json"
        payload = {
            "schema": _SCHEMA,
            "solver": "ElmerFEM",
            "capacitance_matrix_pf": c_pf,
            "provenance": {
                "method": "simulated",
                "source": "ElmerFEM electrostatic solve",
                "confidence": 0.90,
                "artifact": str(dat_file),
            },
        }
        result_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        parsed_data = {
            **solved.parsed_data,
            "capacitance_matrix_pf": c_pf,
            "artifact": str(dat_file),
        }

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="capacitance extracted",
            output_dir=output_dir,
            artifacts={**solved.artifacts, "result_json": result_json},
            parsed_data=parsed_data,
            execution_time_s=solved.execution_time_s,
            version=solved.version,
        )


def _parse_elmer_capacitance(dat_file: Path) -> float:
    """Parse self-capacitance from Elmer .dat file.

    Elmer writes capacitance in SI units (F); convert to pF.
    The standard Elmer capacitance output has format:
        # Time-averaged energy
        # Charge matrix coefficients
        c_11 = <value>   (in SI)
    """
    text = dat_file.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            try:
                value_str = line.split("=")[-1].strip().split()[0]
                val = float(value_str)
                return abs(val) * 1e12  # F → pF
            except (ValueError, IndexError):
                continue
    # If structured differently, try first non-comment numeric line
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                return abs(float(line.split()[0])) * 1e12
            except (ValueError, IndexError):
                continue
    raise ValueError("No capacitance value found in ElmerFEM output")


def _build_geo(
    *,
    width_um: float,
    gap_um: float,
    length_um: float,
    metal_thickness_nm: float,
    device_type: str,
) -> str:
    """Minimal gmsh .geo for a CPW cross-section or IDC finger."""
    t = metal_thickness_nm * 1e-3  # nm → µm
    s = gap_um
    w = width_um
    length = length_um

    return textwrap.dedent(f"""\
        // {device_type} cross-section geometry (all dimensions in µm)
        // Generated by text-to-gds ElmerFEM solver
        SetFactory("OpenCASCADE");
        w = {w};  // conductor width
        s = {s};  // gap
        t = {t};  // metal thickness
        l = {length};  // length

        // Center conductor
        Box(1) = {{0, 0, 0, w, l, t}};
        // Ground plane left
        Box(2) = {{-(w/2 + s), 0, 0, w/2, l, t}};
        // Ground plane right
        Box(3) = {{w + s, 0, 0, w/2, l, t}};
        // Substrate
        Box(4) = {{-(w + 2*s), -l*0.5, -250, 2*(w + 2*s), l*2, 250}};

        Physical Volume("conductor_center") = {{1}};
        Physical Volume("conductor_ground") = {{2, 3}};
        Physical Volume("substrate") = {{4}};
        Mesh.CharacteristicLengthMax = {min(w, s, t) * 0.5:.3f};
        """)


def _build_sif(*, eps_r: float, device_type: str) -> str:
    """Minimal Elmer SIF for electrostatic C-matrix."""
    return textwrap.dedent(f"""\
        ! Elmer SIF — Electrostatic capacitance extraction
        ! Device: {device_type}
        ! Generated by text-to-gds

        Header
          CHECK KEYWORDS Warn
          Mesh DB "." "mesh"
          Results Directory "."
        End

        Simulation
          Max Output Level = 5
          Coordinate System = Cartesian
          Simulation Type = Steady state
          Steady State Max Iterations = 1
          Output Intervals = 1
        End

        Constants
          Permittivity of Vacuum = 8.8542e-12
        End

        Body 1
          Target Bodies(1) = 4  ! substrate
          Equation = 1
          Material = 1
        End

        Body 2
          Target Bodies(2) = 1 2  ! conductors
          Body Force = 1
        End

        Equation 1
          Name = "Electrostatics"
          Active Solvers(1) = 1
        End

        Solver 1
          Equation = Electrostatics
          Procedure = "StatElecSolve" "StatElecSolver"
          Variable = Potential
          Variable DOFs = 1
          Calculate Electric Energy = True
          Calculate Capacitance Matrix = True
          Capacitance Matrix Filename = capacitance.dat
          Linear System Solver = Direct
          Linear System Direct Method = Umfpack
        End

        Material 1
          Name = "Substrate"
          Relative Permittivity = {eps_r}
        End

        Body Force 1
          ! No explicit potential BCs here; handled by Boundary Conditions
        End

        Boundary Condition 1
          Target Boundaries(1) = 1  ! center conductor
          Potential = 1.0
        End

        Boundary Condition 2
          Target Boundaries(2) = 2 3  ! ground planes
          Potential = 0.0
        End
        """)
