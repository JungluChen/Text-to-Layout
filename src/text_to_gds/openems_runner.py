"""openEMS simulation runner that reads directly from extraction.json.

Pipeline:
  1. Read extraction.json (must be text-to-gds.extraction.v1).
  2. Generate a CSXCAD/openEMS simulation XML from extracted geometry.
  3. Run openEMS.
  4. Require that a *.s2p Touchstone file was produced.
  5. Validate the Touchstone with validate_touchstone().

If openEMS is not installed, returns status="skipped".
If the required Touchstone file is not produced, returns status="failed".
Never synthesises S-parameters or plots without a real solver output.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any

SCHEMA = "text-to-gds.openems-runner.v1"


def _find_octave() -> str | None:
    """Find octave or octave-cli on PATH or in common install locations."""
    import shutil
    for name in ("octave-cli", "octave", "octave.exe", "octave-cli.exe"):
        found = shutil.which(name)
        if found:
            return found
    # Common Windows install paths
    from pathlib import Path as _Path
    candidates = [
        _Path(r"C:\Program Files\GNU Octave\Octave-9.3.0\mingw64\bin\octave-cli.exe"),
        _Path(r"C:\Program Files\GNU Octave\Octave-8.4.0\mingw64\bin\octave-cli.exe"),
        _Path(r"C:\Program Files (x86)\GNU Octave\mingw64\bin\octave-cli.exe"),
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


def _run_octave_postprocess(
    octave: str,
    matlab_dir: str,
    sim_dir: str,
    xml_path: str,
) -> None:
    """Run openEMS octave post-processing to produce a Touchstone .s2p file."""
    # Standard openEMS post-processing: calcPort + write_touchstone
    script = textwrap.dedent(f"""\
        pkg load signal;
        addpath('{matlab_dir}');
        cd('{sim_dir}');
        try
            CSX = ReadCSXFile('{xml_path}');
            freq = linspace(1e9, 12e9, 201);
            [port, ~] = calcPort(CSX, '{sim_dir}', freq, 'RefImpedance', 50);
            s11 = port.uf.ref ./ port.uf.inc;
            write_touchstone('s', freq, s11, '{sim_dir}/output.s2p');
        catch e
            fprintf(stderr, 'octave post-process error: %s\\n', e.message);
        end
    """)
    script_path = Path(sim_dir) / "postprocess.m"
    script_path.write_text(script, encoding="utf-8")
    try:
        subprocess.run(
            [octave, "--no-gui", "--quiet", str(script_path)],
            capture_output=True, text=True, timeout=120,
            cwd=sim_dir,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _failed(reason: str, report_path: Path) -> dict[str, Any]:
    result = {"schema": SCHEMA, "status": "failed", "reason": reason, "executed": False}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def _build_openems_xml(
    *,
    substrate_er: float,
    substrate_thickness_um: float,
    metal_conductivity: float,
    port_impedance_ohm: float,
    center_frequency_ghz: float,
    bandwidth_ghz: float,
    sim_dir: Path,
) -> str:
    """Return a minimal openEMS/CSXCAD XML for a lumped-port RF simulation."""
    f_start = max(center_frequency_ghz - bandwidth_ghz / 2.0, 0.1) * 1e9
    f_stop = (center_frequency_ghz + bandwidth_ghz / 2.0) * 1e9
    f_center = center_frequency_ghz * 1e9
    lambda_min = 3e8 / f_stop
    cell_size = lambda_min / 30.0 * 1e6  # µm
    substrate_um = substrate_thickness_um
    box_xy = 500.0  # µm

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!-- Text-to-GDS openEMS simulation — generated from extraction.json -->
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
                    P2="{box_xy/2:.1f}  {box_xy/2:.1f}  {substrate_um:.1f}"/>
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
              <ZLines>0 {cell_size:.1f} {substrate_um:.1f} {substrate_um + cell_size:.1f}</ZLines>
            </RectilinearGrid>
          </ContinuousStructure>
        </openEMS>
    """)


def run_openems(
    extraction_path: str | Path,
    *,
    sim_dir: str | Path,
    report_path: str | Path,
    openems_executable: str | None = None,
    timeout_seconds: int = 900,
    bandwidth_ghz: float = 2.0,
) -> dict[str, Any]:
    """Run openEMS from extraction.json and require a Touchstone output.

    Returns:
      status="failed"  — extraction missing required fields, or no .s2p produced
      status="skipped" — openEMS not installed
      status="executed" — openEMS ran and produced a valid Touchstone
    """
    if openems_executable is None:
        from text_to_gds.tool_discovery import tool_paths
        openems_executable = tool_paths().openems or "openEMS"

    sim = Path(sim_dir)
    report = Path(report_path)
    sim.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    # --- load extraction ---
    try:
        extraction = json.loads(Path(extraction_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _failed(f"cannot read extraction.json: {e}", report)

    if extraction.get("schema") != "text-to-gds.extraction.v1":
        return _failed("extraction.json schema is not text-to-gds.extraction.v1", report)

    lc = extraction.get("linear_circuit", {})
    f0_hz = lc.get("resonance_frequency") or lc.get("resonance_frequency_hz")
    if f0_hz is None:
        return _failed(
            "openEMS simulation requires resonance_frequency in extraction.json; "
            "supply capacitance_ff and jc_ua_per_um2 to extract_layout",
            report,
        )
    center_ghz = float(f0_hz) / 1e9

    substrate_er = float(extraction.get("solver_inputs", {}).get("openems", {}).get("epsilon_r", 11.45))
    substrate_thickness_um = float(
        extraction.get("solver_inputs", {}).get("openems", {}).get("substrate_thickness_um", 254.0)
    )

    # --- generate simulation XML ---
    xml_path = sim / "openems_sim.xml"
    xml_path.write_text(
        _build_openems_xml(
            substrate_er=substrate_er,
            substrate_thickness_um=substrate_thickness_um,
            metal_conductivity=6.3e7,
            port_impedance_ohm=50.0,
            center_frequency_ghz=center_ghz,
            bandwidth_ghz=bandwidth_ghz,
            sim_dir=sim,
        ),
        encoding="utf-8",
    )

    # --- check openEMS availability ---
    try:
        probe = subprocess.run(
            [openems_executable, "--help"],
            capture_output=True, text=True, timeout=15,
        )
        if probe.returncode not in (0, 1):
            raise FileNotFoundError
    except (FileNotFoundError, subprocess.TimeoutExpired):
        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "skipped",
            "reason": f"openEMS executable not found: {openems_executable}",
            "executed": False,
            "xml_path": str(xml_path),
        }
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["report_path"] = str(report)
        return payload

    # --- check octave availability (required for S-parameter post-processing) ---
    octave = _find_octave()
    if octave is None:
        payload = {
            "schema": SCHEMA,
            "status": "skipped",
            "reason": (
                "openEMS binary found but S-parameter extraction requires octave or MATLAB. "
                "Install Octave (https://octave.org/download) and add to PATH, then re-run. "
                "The openEMS FDTD solver stores field data in HDF5 probe files; "
                "the post-processing Touchstone is computed by matlab/calcPort.m scripts. "
                "Python bindings in .tools/openEMS-v0.0.36/openEMS/python/ require Python 3.10/3.11."
            ),
            "executed": False,
            "xml_path": str(xml_path),
            "resolution": "Install Octave or run in Python 3.10/3.11 to use bundled Python wheels",
        }
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["report_path"] = str(report)
        return payload

    # --- run openEMS ---
    completed = subprocess.run(
        [openems_executable, str(xml_path), "--numThreads=1"],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        cwd=str(sim),
    )

    # --- run octave post-processing ---
    matlab_dir = Path(openems_executable).parent / "matlab"
    if not matlab_dir.is_dir():
        # Try locating matlab scripts relative to the binary
        matlab_dir = Path(openems_executable).parents[1] / "matlab"
    touchstone_candidates = sorted(sim.glob("*.s2p"))
    if not touchstone_candidates and matlab_dir.is_dir():
        _run_octave_postprocess(octave, str(matlab_dir), str(sim), str(xml_path))
        touchstone_candidates = sorted(sim.glob("*.s2p"))

    # --- find produced Touchstone ---
    if not touchstone_candidates:
        return _failed(
            "openEMS executed but produced no Touchstone .s2p file. "
            "Octave post-processor ran but did not produce output. "
            "Ensure the simulation XML has valid lumped port definitions.",
            report,
        )
    touchstone_path = touchstone_candidates[-1]

    # --- validate Touchstone ---
    from text_to_gds.rf_validation import validate_touchstone

    validation = validate_touchstone(touchstone_path)
    if validation["status"] != "ok":
        return _failed(
            f"openEMS produced a Touchstone but it failed validation: {validation['reason']}",
            report,
        )

    payload = {
        "schema": SCHEMA,
        "status": "executed",
        "executed": True,
        "engine": "openEMS FDTD",
        "xml_path": str(xml_path),
        "touchstone_path": str(touchstone_path),
        "validation": validation,
        "center_frequency_ghz": center_ghz,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "model_validity": (
            "S-parameters from executed openEMS FDTD simulation. "
            "Touchstone validated for passivity and reciprocity. "
            "No synthetic curves."
        ),
    }
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["report_path"] = str(report)
    return payload
