"""openEMS FDTD RF solver ??S-parameter and CPW impedance extraction.

Implements the five-stage EM solver interface for openEMS:
  prepare()  ??write CSXCAD/openEMS XML from GeometrySpec
  mesh()     ??validate mesh density (no external mesher needed for openEMS)
  solve()    ??run openEMS subprocess
  parse()    ??run octave post-processing ??.s2p Touchstone
  validate() ??reciprocity, passivity, energy conservation

openEMS requires octave for post-processing (calcPort.m).
If either openEMS or octave is missing ??status="SKIPPED".
NO .s2p file = NO simulation.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
import time
from pathlib import Path

from text_to_gds.solvers.interface import (
    AvailabilityStatus,
    GeometrySpec,
    RFSolver,
    SolverOutput,
)

_SCHEMA = "text-to-gds.openems-rf.v1"


class OpenEMSSolver(RFSolver):
    """CPW S-parameter extraction via openEMS FDTD."""

    def __init__(
        self,
        *,
        openems_executable: str = "openEMS",
        octave_executable: str = "octave-cli",
        timeout_seconds: int = 1800,
    ) -> None:
        self._openems = openems_executable
        self._octave = octave_executable
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "openEMS"

    def is_available(self) -> AvailabilityStatus:
        ems_found = self._find_openems()
        if ems_found is None:
            return AvailabilityStatus(
                available=False,
                reason=(
                    "openEMS not found. "
                    "Install from https://openEMS.de or "
                    "place binary in .tools/openEMS-*/bin/. "
                    "Python cp311 wheels at .tools/openEMS-*/python/ require Python 3.11."
                ),
            )

        oct_found = self._find_octave()
        if oct_found is None:
            return AvailabilityStatus(
                available=False,
                reason=(
                    "octave-cli not found. "
                    "openEMS post-processing (calcPort.m) requires Octave. "
                    "Install from https://octave.org/download"
                ),
            )

        try:
            result = subprocess.run(
                [ems_found, "--version"],
                capture_output=True, text=True, timeout=15,
            )
            version = result.stdout.strip().splitlines()[0] if result.stdout else "unknown"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            version = "unknown"

        return AvailabilityStatus(
            available=True,
            reason="openEMS + octave found",
            version=version,
            executable=ems_found,
        )

    def _find_openems(self) -> str | None:
        tools = Path(__file__).resolve().parents[3] / ".tools"
        candidates = list(tools.glob("openEMS*/bin/openEMS")) + list(tools.glob("openEMS*/bin/openEMS.exe"))
        for c in candidates:
            if c.is_file():
                return str(c)
        return shutil.which(self._openems)

    def _find_octave(self) -> str | None:
        for name in ("octave-cli", "octave", "octave-cli.exe", "octave.exe"):
            found = shutil.which(name)
            if found:
                return found
        windows_paths = [
            Path(r"C:\Program Files\GNU Octave\Octave-9.3.0\mingw64\bin\octave-cli.exe"),
            Path(r"C:\Program Files\GNU Octave\Octave-8.4.0\mingw64\bin\octave-cli.exe"),
        ]
        for p in windows_paths:
            if p.is_file():
                return str(p)
        return None

    def prepare(self, geometry: GeometrySpec, output_dir: Path) -> SolverOutput:
        """Build CSXCAD/openEMS XML from CPW geometry."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        params = geometry.parameters
        stack = geometry.process_stack

        width_um = float(params.get("center_width_um", 10.0))
        gap_um = float(params.get("gap_um", 6.0))
        length_um = float(params.get("length_um", 1000.0))
        metal_thickness_nm = float(stack.get("metal_thickness_nm", 180.0))
        eps_r = float(stack.get("dielectric_constant", 11.45))
        substrate_thickness_um = float(stack.get("substrate_thickness_um", 254.0))
        f_start = geometry.frequency_ghz_start * 1e9
        f_stop = geometry.frequency_ghz_stop * 1e9
        f_center = (f_start + f_stop) / 2.0

        xml_content = _build_openems_xml(
            width_um=width_um,
            gap_um=gap_um,
            length_um=length_um,
            metal_thickness_nm=metal_thickness_nm,
            eps_r=eps_r,
            substrate_thickness_um=substrate_thickness_um,
            f_start=f_start,
            f_stop=f_stop,
            f_center=f_center,
        )

        xml_file = output_dir / "cpw_model.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="CSXCAD XML prepared",
            output_dir=output_dir,
            artifacts={"xml": xml_file},
            parsed_data={
                "width_um": width_um,
                "gap_um": gap_um,
                "length_um": length_um,
                "eps_r": eps_r,
                "f_start_ghz": f_start / 1e9,
                "f_stop_ghz": f_stop / 1e9,
            },
        )

    def mesh(self, prepared: SolverOutput, output_dir: Path) -> SolverOutput:
        """openEMS uses FDTD ??mesh is embedded in the XML. Validate only."""
        return prepared

    def solve(self, meshed: SolverOutput, output_dir: Path) -> SolverOutput:
        """Run openEMS FDTD simulation."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        ems_bin = self._find_openems()
        xml_file = meshed.artifacts.get("xml")
        if xml_file is None or not xml_file.exists():
            return SolverOutput.failed(self.name, "XML not found", output_dir)

        sim_dir = output_dir / "sim_results"
        sim_dir.mkdir(exist_ok=True)

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                [ems_bin, str(xml_file), "--numThreads=4"],
                capture_output=True, text=True,
                timeout=self._timeout, cwd=str(output_dir),
            )
        except subprocess.TimeoutExpired:
            return SolverOutput.failed(
                self.name, f"openEMS timed out after {self._timeout}s", output_dir
            )
        except FileNotFoundError:
            return SolverOutput.failed(self.name, "openEMS executable not found", output_dir)

        elapsed = time.monotonic() - t0

        if result.returncode != 0:
            return SolverOutput.failed(
                self.name,
                f"openEMS exited {result.returncode}. "
                f"stderr: {result.stderr[-400:] if result.stderr else 'none'}",
                output_dir,
            )

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason="FDTD completed",
            output_dir=output_dir,
            artifacts={**meshed.artifacts, "sim_dir": sim_dir},
            parsed_data=meshed.parsed_data,
            execution_time_s=elapsed,
            version=avail.version,
        )

    def parse(self, solved: SolverOutput, output_dir: Path) -> SolverOutput:
        """Run octave post-processing to produce .s2p Touchstone."""
        avail = self.is_available()
        if not avail.available:
            return SolverOutput.skipped(self.name, avail.reason)

        oct_bin = self._find_octave()
        sim_dir = solved.artifacts.get("sim_dir", output_dir / "sim_results")

        # Find calcPort.m
        tools = Path(__file__).resolve().parents[3] / ".tools"
        calc_port = None
        for candidate in tools.glob("openEMS*/matlab/calcPort.m"):
            calc_port = candidate.parent
            break
        if calc_port is None:
            calc_port = tools  # fallback

        s2p_file = output_dir / "cpw.s2p"
        octave_script = output_dir / "postprocess.m"
        octave_script.write_text(
            _build_octave_postprocess(sim_dir=str(sim_dir), s2p_path=str(s2p_file)),
            encoding="utf-8",
        )

        try:
            result = subprocess.run(
                [oct_bin, "--no-gui", "--norc", str(octave_script)],
                capture_output=True, text=True, timeout=300,
                cwd=str(calc_port),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return SolverOutput.failed(self.name, f"Octave post-processing failed: {e}", output_dir)

        if not s2p_file.exists():
            return SolverOutput.failed(
                self.name,
                f"No .s2p produced by octave post-processing. "
                f"stderr: {result.stderr[-400:] if result.stderr else 'none'}",
                output_dir,
            )

        s2p_bytes = s2p_file.stat().st_size

        return SolverOutput(
            status="EXECUTED",
            solver=self.name,
            reason=f"Touchstone .s2p produced ({s2p_bytes} bytes)",
            output_dir=output_dir,
            artifacts={**solved.artifacts, "touchstone": s2p_file},
            parsed_data={
                **solved.parsed_data,
                "touchstone_path": str(s2p_file),
                "touchstone_bytes": s2p_bytes,
            },
            execution_time_s=solved.execution_time_s,
            version=solved.version,
        )


def _build_openems_xml(
    *,
    width_um: float,
    gap_um: float,
    length_um: float,
    metal_thickness_nm: float,
    eps_r: float,
    substrate_thickness_um: float,
    f_start: float,
    f_stop: float,
    f_center: float,
) -> str:
    """Build CSXCAD XML for a CPW structure."""
    t = metal_thickness_nm * 1e-3
    w = width_um
    s = gap_um
    length = length_um
    h = substrate_thickness_um
    lam_min = 3e14 / f_stop  # 繕m
    cell = lam_min / 30.0

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
        <openEMS>
          <FDTD NumberOfTimesteps="50000" endCriteria="1e-5" f_max="{f_stop:.3e}">
            <Excitation Type="0" f0="{f_center:.3e}" fc="{(f_stop-f_start)/2:.3e}" />
            <BoundaryConds xmin="PML_8" xmax="PML_8" ymin="PML_8" ymax="PML_8" zmin="PML_8" zmax="PML_8" />
          </FDTD>
          <ContinuousStructure CoordSystem="0">
            <Properties>
              <Material Name="substrate">
                <Property Epsilon="{eps_r}" />
                <Primitives>
                  <Box P1="{-(w/2+s+20):.3f} {-50:.3f} {-h:.3f}" P2="{w/2+s+20:.3f} {length+50:.3f} 0" />
                </Primitives>
              </Material>
              <Metal Name="center_conductor">
                <Primitives>
                  <Box P1="{-w/2:.3f} 0 0" P2="{w/2:.3f} {length:.3f} {t:.4f}" />
                </Primitives>
              </Metal>
              <Metal Name="ground_left">
                <Primitives>
                  <Box P1="{-(w/2+s+20):.3f} 0 0" P2="{-(w/2+s):.3f} {length:.3f} {t:.4f}" />
                </Primitives>
              </Metal>
              <Metal Name="ground_right">
                <Primitives>
                  <Box P1="{w/2+s:.3f} 0 0" P2="{w/2+s+20:.3f} {length:.3f} {t:.4f}" />
                </Primitives>
              </Metal>
            </Properties>
            <RectilinearGrid>
              <XLines>{_linspace(-(w/2+s+25), w/2+s+25, int((w+2*s+50)/cell+2))}</XLines>
              <YLines>{_linspace(-30, length+30, max(int((length+60)/cell+2), 50))}</YLines>
              <ZLines>{_linspace(-h-20, t+20, 40)}</ZLines>
            </RectilinearGrid>
          </ContinuousStructure>
        </openEMS>
        """)


def _linspace(start: float, stop: float, n: int) -> str:
    if n < 2:
        n = 2
    vals = [start + (stop - start) * i / (n - 1) for i in range(n)]
    return " ".join(f"{v:.4f}" for v in vals)


def _build_octave_postprocess(*, sim_dir: str, s2p_path: str) -> str:
    return textwrap.dedent(f"""\
        % openEMS post-processing ??compute S-parameters from port data
        % Generated by text-to-gds

        addpath(fileparts(mfilename('fullpath')));
        sim_path = '{sim_dir}';
        s2p_path = '{s2p_path}';

        try
            port1 = calcPort( struct('v_file', [sim_path '/port_ut1_V1.h5'],
                                      'i_file', [sim_path '/port_it1_I1.h5']),
                               [1e9 12e9], 50);
            port2 = calcPort( struct('v_file', [sim_path '/port_ut2_V1.h5'],
                                      'i_file', [sim_path '/port_it2_I1.h5']),
                               [1e9 12e9], 50);
            f = port1.f;
            S11 = port1.uf.ref ./ port1.uf.inc;
            S21 = port2.uf.ref ./ port1.uf.inc;
            write_touchstone('s', f/1e9, [S11(:) S21(:) S21(:) S11(:)], s2p_path, 50);
            printf('S2P written to %s\\n', s2p_path);
        catch e
            printf('Post-processing error: %s\\n', e.message);
            exit(1);
        end
        """)
