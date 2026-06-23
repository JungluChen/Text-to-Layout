from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Any

from text_to_gds.simulation.solver_adapter import BaseSolverAdapter


class OpenEMSAdapter(BaseSolverAdapter):
    def __init__(
        self,
        executable: str = "openEMS",
        *,
        timeout_seconds: int = 900,
    ) -> None:
        super().__init__(solver_name="openEMS", executable=executable)
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        tools_root = Path(__file__).resolve().parents[3] / ".tools"
        if (tools_root / "openems-venv").exists():
            return True
        try:
            from importlib.util import find_spec

            if find_spec("openEMS") is not None:
                return True
        except (ModuleNotFoundError, ValueError):
            pass
        try:
            result = subprocess.run(
                [self.executable, "--help"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.returncode in (0, 1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _generate_input(
        self,
        input_data: dict[str, Any],
        *,
        output_dir: Path,
    ) -> Path:
        substrate_er = float(input_data.get("epsilon_r", 11.45))
        substrate_thickness_um = float(input_data.get("substrate_thickness_um", 254.0))
        metal_conductivity = float(input_data.get("metal_conductivity", 6.3e7))
        center_frequency_ghz = float(input_data.get("center_frequency_ghz", 6.0))
        bandwidth_ghz = float(input_data.get("bandwidth_ghz", 2.0))

        f_start = max(center_frequency_ghz - bandwidth_ghz / 2.0, 0.1) * 1e9
        f_stop = (center_frequency_ghz + bandwidth_ghz / 2.0) * 1e9
        f_center = center_frequency_ghz * 1e9
        lambda_min = 3e8 / f_stop
        cell_size = lambda_min / 30.0 * 1e6
        box_xy = 500.0

        xml = textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-8"?>
            <openEMS>
              <FDTD NumberOfTimesteps="1000000" endCriteria="1e-5">
                <Excitation Type="0" f0="{f_center:.6g}" fc="{(f_stop - f_start)/2:.6g}"/>
                <BoundaryCond xmin="PML_8" xmax="PML_8"
                              ymin="PML_8" ymax="PML_8"
                              zmin="PEC"   zmax="PML_8"/>
              </FDTD>
              <ContinuousStructure CoordSystem="0">
                <Properties>
                  <Material name="substrate">
                    <Property Epsilon="{substrate_er:.4g}" Mue="1.0"/>
                    <Primitives>
                      <Box Priority="1"
                        P1="{-box_xy/2:.1f} {-box_xy/2:.1f} 0"
                        P2="{box_xy/2:.1f}  {box_xy/2:.1f}  {substrate_thickness_um:.1f}"/>
                    </Primitives>
                  </Material>
                  <Metal name="ground_plane">
                    <Property Sigma="{metal_conductivity:.4g}"/>
                    <Primitives>
                      <Box Priority="5"
                        P1="{-box_xy/2:.1f} {-box_xy/2:.1f} 0"
                        P2="{box_xy/2:.1f}  {box_xy/2:.1f}  0"/>
                    </Primitives>
                  </Metal>
                </Properties>
                <RectilinearGrid DeltaUnit="1e-6">
                  <XLines>{-box_xy/2:.1f} {-cell_size:.1f} 0 {cell_size:.1f} {box_xy/2:.1f}</XLines>
                  <YLines>{-box_xy/2:.1f} {-cell_size:.1f} 0 {cell_size:.1f} {box_xy/2:.1f}</YLines>
                  <ZLines>0 {cell_size:.1f} {substrate_thickness_um:.1f} {substrate_thickness_um + cell_size:.1f}</ZLines>
                </RectilinearGrid>
              </ContinuousStructure>
            </openEMS>
        """)

        xml_path = output_dir / "openems_sim.xml"
        xml_path.write_text(xml, encoding="utf-8")
        return xml_path

    def _run_solver(self, input_path: Path) -> None:
        result = subprocess.run(
            [self.executable, str(input_path), "--numThreads=1"],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            cwd=str(input_path.parent),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"openEMS exited with code {result.returncode}: "
                f"{result.stderr[-500:]}"
            )

    def _parse_output(self, output_path: Path) -> dict[str, Any]:
        sim_dir = output_path.parent
        touchstones = sorted(sim_dir.glob("*.s2p"))
        if not touchstones:
            return {"status": "no_touchstone", "touchstone_path": None}

        touchstone_path = touchstones[-1]
        s_params = self._parse_touchstone(touchstone_path)
        return {
            "status": "parsed",
            "touchstone_path": str(touchstone_path),
            "s_parameters": s_params,
        }

    def _validate_output(self, parsed: dict[str, Any]) -> bool:
        return parsed.get("status") == "parsed" and parsed.get("touchstone_path") is not None

    def _parse_touchstone(self, path: Path) -> dict[str, Any]:
        frequencies: list[float] = []
        s11: list[complex] = []
        s21: list[complex] = []

        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("!") or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 5:
                continue
            try:
                freq = float(parts[0])
                re11, im11 = float(parts[1]), float(parts[2])
                re21, im21 = float(parts[3]), float(parts[4])
            except (ValueError, IndexError):
                continue
            frequencies.append(freq)
            s11.append(complex(re11, im11))
            s21.append(complex(re21, im21))

        return {
            "frequencies_hz": frequencies,
            "s11": [{"re": c.real, "im": c.imag} for c in s11],
            "s21": [{"re": c.real, "im": c.imag} for c in s21],
        }
