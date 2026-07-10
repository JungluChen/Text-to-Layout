from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from textlayout._legacy.integrations import list_research_integrations
from textlayout._legacy.simulation import (
    PHI0_WEBER,
    PLANCK_J_S,
    estimate_physical_performance,
    simulate_ideal_junction,
)

ELECTRON_CHARGE_C = 1.602176634e-19
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_TOOLS_ROOT = Path(os.environ.get("TEXT_TO_GDS_TOOLS", PROJECT_ROOT / ".tools")).resolve()


def _find_openems_runtime() -> tuple[str | None, str | None]:
    """Return (python_executable, dll_bin_dir) for a local openEMS install, if present.

    On Windows openEMS ships as a binary release with cp310/cp311 wheels, so the project
    keeps a dedicated interpreter under .tools/openems-venv plus the unpacked binaries.
    """
    python_override = os.environ.get("TEXT_TO_GDS_OPENEMS_PYTHON")
    bin_override = os.environ.get("TEXT_TO_GDS_OPENEMS_BIN")
    python_candidates: list[Path] = []
    if python_override:
        python_candidates.append(Path(python_override))
    python_candidates.append(LOCAL_TOOLS_ROOT / "openems-venv" / "Scripts" / "python.exe")
    python_candidates.append(LOCAL_TOOLS_ROOT / "openems-venv" / "bin" / "python")
    python_path = next((str(path) for path in python_candidates if path.exists()), None)

    bin_candidates: list[Path] = []
    if bin_override:
        bin_candidates.append(Path(bin_override))
    bin_candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("openEMS*/openEMS"), reverse=True))
    bin_candidates.extend(sorted(LOCAL_TOOLS_ROOT.glob("openEMS*"), reverse=True))
    bin_path = next((str(path) for path in bin_candidates if path.exists()), None)

    # Fall back to an importable openEMS in the current interpreter (e.g. Linux installs).
    if python_path is None and find_spec("openEMS") is not None:
        python_path = sys.executable
    return python_path, bin_path


def _integration(id_value: str) -> dict[str, Any]:
    for integration in list_research_integrations():
        if integration["id"] == id_value:
            return integration
    return {"id": id_value, "installed": False}


def _ports(sidecar: dict[str, Any]) -> list[dict[str, Any]]:
    return [port for port in sidecar.get("ports", []) if isinstance(port, dict)]


def _target_value(sidecar: dict[str, Any], key: str, explicit: float | None, default: float) -> float:
    if explicit is not None:
        return float(explicit)
    info = sidecar.get("info", {})
    value = info.get(key)
    return float(value) if value is not None else default


def _center_frequency_from_simulation(
    sidecar: dict[str, Any],
    simulation: dict[str, Any] | None = None,
) -> float:
    if isinstance(simulation, dict):
        physical = simulation.get("physical_performance")
        if isinstance(physical, dict):
            flux = physical.get("flux_tuning")
            if isinstance(flux, dict):
                operating = flux.get("operating_point")
                if isinstance(operating, dict) and operating.get("resonant_frequency_ghz") is not None:
                    return float(operating["resonant_frequency_ghz"])
            if physical.get("center_frequency_ghz") is not None:
                return float(physical["center_frequency_ghz"])
    return _target_value(sidecar, "center_frequency_ghz", None, 5.0)


def _openems_script_text(config: dict[str, Any], *, result_path: Path, bin_dir: str, plot_path: Path | None) -> str:
    """Build a self-contained, runnable openEMS FDTD microstrip-extraction script."""
    header = (
        "# Text-to-GDS generated openEMS FDTD runner (executed for real when openEMS is present).\n"
        "import os, sys, json, glob, tempfile\n"
        f"CONFIG = json.loads({json.dumps(json.dumps(config))})\n"
        f"RESULT_PATH = {json.dumps(str(result_path))}\n"
        f"BIN_DIR = {json.dumps(bin_dir or '')}\n"
        f"PLOT_PATH = {json.dumps(str(plot_path) if plot_path else '')}\n"
    )
    body = '''
if BIN_DIR and os.path.isdir(BIN_DIR):
    try:
        os.add_dll_directory(BIN_DIR)
    except (AttributeError, OSError):
        pass
    os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ.get("PATH", "")

import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import C0

w = float(CONFIG["trace_width_um"])
L = float(CONFIG["line_length_um"])
h = float(CONFIG["substrate_thickness_um"])
epr = float(CONFIG["substrate_epsilon"])
f_max = float(CONFIG["f_max_hz"])
div = float(CONFIG["mesh_div"])
nrts = int(CONFIG["nrts"])
freq_points = int(CONFIG["freq_points"])

FDTD = openEMS(EndCriteria=1e-4, NrTS=nrts)
FDTD.SetGaussExcite(f_max / 2.0, f_max / 2.0)
FDTD.SetBoundaryCond(["PML_8", "PML_8", "MUR", "MUR", "PEC", "MUR"])
CSX = ContinuousStructure()
FDTD.SetCSX(CSX)
mesh = CSX.GetGrid()
mesh.SetDeltaUnit(1e-6)
res = C0 / (f_max * np.sqrt(epr)) / 1e-6 / div
third = np.array([2 * res / 3, -res / 3]) / 4
mesh.AddLine("x", 0)
mesh.AddLine("x", w / 2 + third)
mesh.AddLine("x", -w / 2 - third)
mesh.SmoothMeshLines("x", res / 4)
mesh.AddLine("x", [-L, L])
mesh.SmoothMeshLines("x", res)
mesh.AddLine("y", 0)
mesh.AddLine("y", w / 2 + third)
mesh.AddLine("y", -w / 2 - third)
mesh.SmoothMeshLines("y", res / 4)
mesh.AddLine("y", [-15 * w, 15 * w])
mesh.SmoothMeshLines("y", res)
mesh.AddLine("z", np.linspace(0, h, 5))
mesh.AddLine("z", 12 * h)
mesh.SmoothMeshLines("z", res)
substrate = CSX.AddMaterial("substrate", epsilon=epr)
substrate.AddBox([-L, -15 * w, 0], [L, 15 * w, h])
pec = CSX.AddMetal("PEC")
Et = CSX.AddDump("Et", dump_type=0, file_type=0)
Et.AddBox([-L, -15 * w, h], [L, 15 * w, h])
p0 = FDTD.AddMSLPort(1, pec, [-L, -w / 2, h], [0, w / 2, 0], "x", "z",
                     excite=-1, FeedShift=10 * res, MeasPlaneShift=L / 3, priority=10)
p1 = FDTD.AddMSLPort(2, pec, [L, -w / 2, h], [0, w / 2, 0], "x", "z",
                     MeasPlaneShift=L / 3, priority=10)
sim_dir = CONFIG.get("sim_dir") or tempfile.mkdtemp(prefix="text_to_gds_openems_")
os.makedirs(sim_dir, exist_ok=True)
FDTD.Run(sim_dir, cleanup=False)
f = np.linspace(1e6, f_max, freq_points)
p0.CalcPort(sim_dir, f, ref_impedance=50)
p1.CalcPort(sim_dir, f, ref_impedance=50)
s11 = p0.uf_ref / p0.uf_inc
s21 = p1.uf_ref / p0.uf_inc
beta = np.abs(np.real(p0.beta))
omega = 2 * np.pi * f
# p0.beta is the phase constant in rad/m.  Therefore beta*c/omega is
# dimensionless and eps_eff = (c/v_phase)^2 = (beta*c/omega)^2.
eps_eff = (beta * C0 / omega) ** 2
z0_est = np.abs(p0.uf_tot / p0.if_tot)
s11_db = (20 * np.log10(np.maximum(np.abs(s11), 1e-12))).tolist()
s21_db = (20 * np.log10(np.maximum(np.abs(s21), 1e-12))).tolist()
mid = len(f) // 2
power_sum = np.abs(s11) ** 2 + np.abs(s21) ** 2
passivity_residual = 1.0 - power_sum
valid_frequency_min_hz = max(0.5e9, 0.1 * f_max)
valid_band = f >= valid_frequency_min_hz
valid_eps = np.isfinite(eps_eff) & valid_band
passivity_passed = bool(np.min(passivity_residual[valid_band]) >= -0.02)
permittivity_passed = bool(
    np.all((eps_eff[valid_eps] >= 1.0) & (eps_eff[valid_eps] <= epr))
)
field_files = sorted(glob.glob(os.path.join(sim_dir, "Et*")))
result = {
    "schema": "text-to-gds.openems-project.v0",
    "adapter": "openEMS",
    "analysis_status": "validated" if passivity_passed and permittivity_passed else "invalid",
    "engine": "openEMS FDTD (microstrip-port impedance/S-parameter extraction)",
    "geometry": {
        "trace_width_um": w,
        "line_length_um": L,
        "substrate_thickness_um": h,
        "substrate_epsilon": epr,
        "mesh_resolution_um": float(res),
    },
    "frequencies_ghz": (f / 1e9).tolist(),
    "s11_db": s11_db,
    "s21_db": s21_db,
    "effective_permittivity": eps_eff.tolist(),
    "effective_permittivity_midband": float(eps_eff[mid]),
    "characteristic_impedance_ohm_estimate": float(np.median(z0_est)),
    "return_loss_db_midband": float(s11_db[mid]),
    "insertion_loss_db_midband": float(s21_db[mid]),
    "guided_wavelength_um_midband": float(2 * np.pi / beta[mid] / 1e-6) if beta[mid] else None,
    "power_conservation_residual": passivity_residual.tolist(),
    "passivity_check": {
        "valid_frequency_min_ghz": float(valid_frequency_min_hz / 1e9),
        "maximum_power_sum": float(np.max(power_sum[valid_band])),
        "minimum_residual": float(np.min(passivity_residual[valid_band])),
        "passed": passivity_passed,
    },
    "effective_permittivity_check": {
        "valid_frequency_min_ghz": float(valid_frequency_min_hz / 1e9),
        "minimum": float(np.min(eps_eff[valid_eps])),
        "maximum": float(np.max(eps_eff[valid_eps])),
        "expected_bounds": [1.0, epr],
        "passed": permittivity_passed,
    },
    "equations": {
        "angular_frequency": "omega = 2*pi*f",
        "effective_permittivity": "epsilon_eff = (c0*beta/omega)^2",
        "passive_power_bound": "|S11|^2 + |S21|^2 <= 1",
    },
    "sim_dir": sim_dir,
    "field_dump_files": field_files,
    "model_validity": (
        "Real openEMS FDTD run using a microstrip-port approximation of the requested trace. "
        "Effective permittivity is extracted from the simulated propagation constant; "
        "S-parameters, Z0, and field dumps are line-extraction estimates pending coplanar ports and a "
        "superconducting-metal (kinetic-inductance) model."
    ),
}
with open(RESULT_PATH, "w") as handle:
    json.dump(result, handle, indent=2)
if PLOT_PATH:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.4), constrained_layout=True)
    axes[0].plot(f / 1e9, s21_db, linewidth=1.8, label="S21")
    axes[0].plot(f / 1e9, s11_db, linewidth=1.8, label="S11")
    axes[0].set_xlabel("Frequency (GHz)")
    axes[0].set_ylabel("Magnitude (dB)")
    axes[0].set_title("openEMS S-parameters")
    axes[0].legend(loc="best")
    # eps_eff = (beta*c/omega)^2 is ill-conditioned as f -> 0, so mask low frequency.
    mask = valid_eps
    axes[1].plot(f[mask] / 1e9, eps_eff[mask], linewidth=1.8, color="#ff9f0a")
    if mask.any():
        eps_mid = float(np.median(eps_eff[mask]))
        axes[1].set_ylim(0.0, max(epr * 1.1, eps_mid * 1.2, 1.0))
    axes[1].set_xlabel("Frequency (GHz)")
    axes[1].set_ylabel("Effective permittivity")
    axes[1].set_title("epsilon_eff = (c0 * beta / omega)^2")
    axes[2].plot(f / 1e9, power_sum, linewidth=1.8, color="#7c3aed")
    axes[2].axhline(1.0, color="#dc2626", linestyle="--", linewidth=1.2, label="passive bound")
    axes[2].axvspan(0.0, valid_frequency_min_hz / 1e9, color="#94a3b8", alpha=0.2,
                    label="below validated band")
    axes[2].set_xlabel("Frequency (GHz)")
    axes[2].set_ylabel("|S11|^2 + |S21|^2")
    axes[2].set_title("Power-conservation check")
    axes[2].legend(loc="best")
    fig.suptitle("openEMS microstrip extraction (requested geometry)")
    fig.savefig(PLOT_PATH, dpi=220)
print("text_to_gds_openems_done", RESULT_PATH)
'''
    return header + body


def write_openems_project(
    sidecar: dict[str, Any],
    *,
    script_path: str | Path,
    report_path: str | Path,
    result_path: str | Path | None = None,
    plot_path: str | Path | None = None,
    target_frequency_ghz: float | None = None,
    substrate_epsilon: float = 11.45,
    substrate_thickness_um: float = 254.0,
    mesh_div: int = 40,
    run: bool = True,
    timeout_seconds: int = 420,
) -> dict[str, Any]:
    """Generate and (when openEMS is installed) execute a real CPW/microstrip EM extraction.

    Falls back to writing the runnable script only, with status ``skipped``, when no local
    openEMS runtime is found.
    """
    script = Path(script_path)
    report = Path(report_path)
    result_file = Path(result_path) if result_path is not None else report.with_suffix(".result.json")
    plot = Path(plot_path) if plot_path is not None else None
    for path in (script, report, result_file):
        path.parent.mkdir(parents=True, exist_ok=True)
    # openEMS' FDTD.Run() changes the working directory, so bake absolute output paths.
    result_file = result_file.resolve()
    if plot is not None:
        plot.parent.mkdir(parents=True, exist_ok=True)
        plot = plot.resolve()

    info = sidecar.get("info", {})
    center_ghz = _target_value(sidecar, "center_frequency_ghz", target_frequency_ghz, 5.0)
    requested_width = float(info.get("cpw_trace_width_um", info.get("trace_width_um", 10.0)))
    # Preserve the requested geometry.  Replacing a narrow trace by a 200 um surrogate changes
    # impedance and invalidates any claim that the result belongs to the source layout.
    sim_width = requested_width
    f_max_hz = max(2.0 * center_ghz, 12.0) * 1e9
    line_length_um = min(max(60.0 * sim_width, 15000.0), 24000.0)
    config = {
        "trace_width_um": sim_width,
        "requested_trace_width_um": requested_width,
        "line_length_um": line_length_um,
        "substrate_thickness_um": float(substrate_thickness_um),
        "substrate_epsilon": float(substrate_epsilon),
        "f_max_hz": f_max_hz,
        "mesh_div": int(mesh_div),
        "nrts": 60000,
        "freq_points": 201,
        "center_frequency_ghz": center_ghz,
    }

    python_exe, bin_dir = _find_openems_runtime()
    script.write_text(
        _openems_script_text(config, result_path=result_file, bin_dir=bin_dir or "", plot_path=plot),
        encoding="utf-8",
    )

    base = {
        "schema": "text-to-gds.openems-project.v0",
        "integration": _integration("openems"),
        "script_path": str(script),
        "report_path": str(report),
        "result_path": str(result_file),
        "plot_path": str(plot) if plot else None,
        "source_gds": sidecar.get("gds_path"),
        "config": config,
        "ports": _ports(sidecar),
        "model": {"ports": _ports(sidecar), "config": config},
        "openems_python": python_exe,
        "openems_bin_dir": bin_dir,
    }

    if not run or python_exe is None:
        result = {
            **base,
            "status": "skipped",
            "executed": False,
            "model_validity": (
                "openEMS runtime not found; generated a runnable FDTD script. Install the "
                "Windows openEMS release into .tools/openems-venv or set "
                "TEXT_TO_GDS_OPENEMS_PYTHON to execute it."
            ),
        }
        report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    env = dict(os.environ)
    if bin_dir:
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    completed = subprocess.run(
        [python_exe, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=env,
    )
    execution: dict[str, Any] | None = None
    if result_file.exists():
        try:
            execution = json.loads(result_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            execution = None
    status = "executed" if completed.returncode == 0 and execution is not None else "failed"
    result = {
        **base,
        "status": status,
        "executed": True,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
        "execution": execution,
        "model_validity": (
            execution.get("model_validity")
            if isinstance(execution, dict)
            else "openEMS run did not produce a result file; see stderr_tail."
        ),
    }
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _execute_qcodes(
    plan: dict[str, Any],
    *,
    db_path: Path,
    plot_path: Path | None,
    center_ghz: float,
    bandwidth_mhz: float,
    peak_gain_db: float,
    sample_name: str,
) -> dict[str, Any]:
    """Actually run QCoDeS when installed: record a mock-VNA sweep into a real dataset.

    No laboratory hardware is touched. A synthetic VNA-style instrument produces the
    S-parameter data so the QCoDeS Measurement/DataSet stack runs end to end and writes
    a genuine SQLite experiment database that a lab can later repoint at real drivers.
    """
    if find_spec("qcodes") is None:
        return {
            "status": "skipped",
            "reason": "qcodes is not installed; install with: py -3 -m uv sync --extra measurement",
        }
    try:
        import numpy as np
        import qcodes as qc
        from qcodes.dataset import (
            Measurement,
            initialise_or_create_database_at,
            load_or_create_experiment,
        )
        from qcodes.parameters import Parameter

        sweep = plan["frequency_sweep"]
        start_hz = float(sweep["start_ghz"]) * 1e9
        stop_hz = float(sweep["stop_ghz"]) * 1e9
        n_points = min(int(sweep.get("points", 401)), 401)
        freqs = np.linspace(start_hz, stop_hz, n_points)
        bw_hz = max(bandwidth_mhz, 1.0) * 1e6
        center_hz = center_ghz * 1e9
        denom = 1.0 + (2.0 * (freqs - center_hz) / bw_hz) ** 2
        s21 = peak_gain_db - 10.0 * np.log10(denom)
        s11 = np.minimum(-3.0, -12.0 + 0.35 * 10.0 * np.log10(denom))

        db_path.parent.mkdir(parents=True, exist_ok=True)
        initialise_or_create_database_at(str(db_path))
        experiment = load_or_create_experiment(
            experiment_name="text_to_gds_ljpa",
            sample_name=sample_name,
        )
        frequency = Parameter("frequency", label="Frequency", unit="Hz", set_cmd=None, get_cmd=None)
        s21_param = Parameter("s21", label="S21", unit="dB", set_cmd=None, get_cmd=None)
        s11_param = Parameter("s11", label="S11", unit="dB", set_cmd=None, get_cmd=None)
        measurement = Measurement(exp=experiment, name="vna_s_parameter_sweep")
        measurement.register_parameter(frequency)
        measurement.register_parameter(s21_param, setpoints=(frequency,))
        measurement.register_parameter(s11_param, setpoints=(frequency,))
        with measurement.run() as datasaver:
            for index in range(n_points):
                datasaver.add_result(
                    (frequency, float(freqs[index])),
                    (s21_param, float(s21[index])),
                    (s11_param, float(s11[index])),
                )
            dataset = datasaver.dataset

        read_back = dataset.get_parameter_data("s21").get("s21", {})
        recorded_points = int(len(read_back.get("s21", []))) if read_back else n_points

        if plot_path is not None:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            plot_path.parent.mkdir(parents=True, exist_ok=True)
            plt.style.use("seaborn-v0_8-whitegrid")
            fig, axis = plt.subplots(figsize=(8.4, 5.0), constrained_layout=True)
            axis.plot(freqs / 1e9, s21, linewidth=1.8, label="S21")
            axis.plot(freqs / 1e9, s11, linewidth=1.8, label="S11")
            axis.set_xlabel("Frequency (GHz)")
            axis.set_ylabel("Magnitude (dB)")
            axis.set_title(f"QCoDeS recorded sweep (run {dataset.run_id})")
            axis.legend(loc="best")
            fig.savefig(plot_path, dpi=220)
            plt.close(fig)

        return {
            "status": "executed",
            "engine": f"qcodes {qc.__version__}",
            "instrument": "synthetic VNA (mock data; no laboratory hardware accessed)",
            "database_path": str(db_path),
            "experiment_name": experiment.name,
            "sample_name": sample_name,
            "run_id": int(dataset.run_id),
            "guid": str(dataset.guid),
            "captured_parameters": ["frequency", "s21", "s11"],
            "recorded_points": recorded_points,
            "plot_path": str(plot_path) if plot_path is not None else None,
        }
    except Exception as error:  # pragma: no cover - depends on optional package details.
        return {"status": "failed", "error": f"{type(error).__name__}: {error}"}


def write_measurement_plan(
    sidecar: dict[str, Any],
    *,
    plan_path: str | Path,
    script_path: str | Path,
    db_path: str | Path | None = None,
    plot_path: str | Path | None = None,
    simulation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a QCoDeS-style lab measurement plan without touching instruments."""
    plan_file = Path(plan_path)
    script = Path(script_path)
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    script.parent.mkdir(parents=True, exist_ok=True)

    center_ghz = _center_frequency_from_simulation(sidecar, simulation)
    physical = simulation.get("physical_performance", {}) if isinstance(simulation, dict) else {}
    bandwidth_mhz = (
        float(physical.get("bandwidth_3db_mhz"))
        if isinstance(physical, dict) and physical.get("bandwidth_3db_mhz") is not None
        else _target_value(sidecar, "target_bandwidth_mhz", None, 500.0)
    )
    span_ghz = max(2.0 * bandwidth_mhz / 1000.0, 0.2)
    frequency_start_ghz = max(center_ghz - span_ghz / 2.0, 0.001)
    frequency_stop_ghz = center_ghz + span_ghz / 2.0
    plan = {
        "schema": "text-to-gds.measurement-plan.v0",
        "integration": _integration("qcodes"),
        "source_gds": sidecar.get("gds_path"),
        "ports": _ports(sidecar),
        "frequency_sweep": {
            "start_ghz": frequency_start_ghz,
            "stop_ghz": frequency_stop_ghz,
            "points": 401,
            "vna_ports": ["rf_in", "rf_out"],
            "power_dbm": -130.0,
        },
        "pump_sweep": {
            "enabled": sidecar.get("pcell") == "lumped_element_jpa_seed",
            "frequency_ghz": 2.0 * center_ghz,
            "power_dbm": [-90, -80, -70, -60],
        },
        "flux_sweep": {
            "enabled": bool(sidecar.get("info", {}).get("squid_enabled")),
            "bias_phi0": [-0.5, -0.25, 0.0, 0.25, 0.5],
        },
        "recorded_metrics": [
            "S11",
            "S21",
            "gain",
            "bandwidth_3db_mhz",
            "input_1db_compression_dbm",
            "noise_temperature_k",
            "pump_power_dbm",
            "flux_bias",
        ],
        "safety": [
            "Use cryostat and device-specific attenuation limits.",
            "Start below expected compression power and increase slowly.",
            "Log fridge temperature and magnet current with each sweep.",
        ],
    }
    plan_file.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    script.write_text(
        f'''# Text-to-GDS generated QCoDeS measurement-plan skeleton.
from __future__ import annotations

import json
from pathlib import Path

PLAN_PATH = Path({json.dumps(str(plan_file))})


def main() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    try:
        import qcodes as qc
    except ImportError as error:
        raise SystemExit(f"QCoDeS is not installed: {{error}}")

    experiment = qc.load_or_create_experiment(
        experiment_name="text_to_gds_ljpa",
        sample_name=Path(plan.get("source_gds") or "unknown").stem,
    )
    print(f"Loaded experiment {{experiment.name}}")
    print("Attach VNA, pump source, flux source, and fridge instruments here.")
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )
    peak_gain_db = (
        float(physical.get("estimated_peak_gain_db"))
        if isinstance(physical, dict) and physical.get("estimated_peak_gain_db") is not None
        else float(sidecar.get("info", {}).get("target_gain_db", 20.0))
    )
    sample_name = Path(sidecar.get("gds_path") or "unknown").stem
    execution = _execute_qcodes(
        plan,
        db_path=Path(db_path) if db_path is not None else plan_file.with_suffix(".qcodes.db"),
        plot_path=Path(plot_path) if plot_path is not None else None,
        center_ghz=center_ghz,
        bandwidth_mhz=bandwidth_mhz,
        peak_gain_db=peak_gain_db,
        sample_name=sample_name,
    )
    plan["execution"] = execution
    plan["script_path"] = str(script)
    plan["plan_path"] = str(plan_file)
    plan_file.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan


def _write_scqubits_plot(plot_path: Path, execution: dict[str, Any], qubit_type: str) -> None:
    """Render a scqubits energy-level + dispersion figure from computed data."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.4), constrained_layout=True)

    levels = execution.get("energy_levels_ghz") or []
    axes[0].bar(range(len(levels)), levels, color="#3866d6")
    axes[0].set_xlabel("level n")
    axes[0].set_ylabel("E_n - E_0 (GHz)")
    axes[0].set_title(f"{qubit_type} energy levels")

    dispersion = execution.get("flux_spectrum") or execution.get("charge_dispersion")
    if dispersion:
        x_key = "flux_phi0" if "flux_spectrum" in execution else "ng"
        x = dispersion.get(x_key, [])
        for key in ("f01_ghz", "f02_ghz", "f03_ghz"):
            if key in dispersion:
                axes[1].plot(x, dispersion[key], linewidth=1.8, label=key.replace("_ghz", ""))
        axes[1].set_xlabel("flux (Phi0)" if x_key == "flux_phi0" else "ng")
        axes[1].set_ylabel("transition frequency (GHz)")
        axes[1].set_title("Spectrum vs bias")
        axes[1].legend(loc="best")
    else:
        axes[1].text(0.5, 0.5, "no dispersion data", ha="center", va="center")
        axes[1].set_axis_off()

    fig.suptitle("Text-to-GDS scqubits Hamiltonian", fontsize=13)
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def _execute_scqubits(
    *,
    ej_ghz: float | None,
    ec_ghz: float | None,
    uses_squid: bool,
    flux_bias_phi0: float,
    squid_asymmetry: float,
    plot_path: Path | None,
) -> dict[str, Any]:
    """Actually run scqubits when installed: build the qubit and compute the spectrum."""
    if find_spec("scqubits") is None:
        return {
            "status": "skipped",
            "reason": "scqubits is not installed; install with: py -3 -m uv sync --extra quantum",
        }
    if ej_ghz is None or ec_ghz is None or ej_ghz <= 0.0 or ec_ghz <= 0.0:
        return {
            "status": "skipped",
            "reason": "Need finite positive EJ and EC (non-zero junction area and capacitance).",
        }
    try:
        import numpy as np
        import scqubits as scq

        ncut = 51 if ej_ghz / ec_ghz > 80.0 else 31
        evals_count = 6
        if uses_squid:
            qubit = scq.TunableTransmon(
                EJmax=float(ej_ghz),
                EC=float(ec_ghz),
                d=float(squid_asymmetry),
                flux=float(flux_bias_phi0),
                ng=0.0,
                ncut=ncut,
            )
            qubit_type = "TunableTransmon"
        else:
            qubit = scq.Transmon(EJ=float(ej_ghz), EC=float(ec_ghz), ng=0.0, ncut=ncut)
            qubit_type = "Transmon"

        evals = np.asarray(qubit.eigenvals(evals_count=evals_count), dtype=float)
        levels = (evals - evals[0]).tolist()
        execution: dict[str, Any] = {
            "status": "executed",
            "engine": f"scqubits {scq.__version__}",
            "qubit_type": qubit_type,
            "ncut": ncut,
            "operating_point": {
                "flux_phi0": float(flux_bias_phi0) if uses_squid else None,
                "ng": 0.0,
            },
            "energy_levels_ghz": levels,
            "f01_ghz": float(evals[1] - evals[0]),
            "f12_ghz": float(evals[2] - evals[1]),
            "anharmonicity_ghz": float(qubit.anharmonicity()),
        }
        if uses_squid:
            flux_points = np.linspace(-0.5, 0.5, 51)
            table = np.asarray(
                qubit.get_spectrum_vs_paramvals(
                    "flux", flux_points, evals_count=4, subtract_ground=True
                ).energy_table,
                dtype=float,
            )
            execution["flux_spectrum"] = {
                "flux_phi0": flux_points.tolist(),
                "f01_ghz": table[:, 1].tolist(),
                "f02_ghz": table[:, 2].tolist(),
                "f03_ghz": table[:, 3].tolist(),
            }
        else:
            ng_points = np.linspace(-1.0, 1.0, 51)
            table = np.asarray(
                qubit.get_spectrum_vs_paramvals(
                    "ng", ng_points, evals_count=4, subtract_ground=True
                ).energy_table,
                dtype=float,
            )
            execution["charge_dispersion"] = {
                "ng": ng_points.tolist(),
                "f01_ghz": table[:, 1].tolist(),
                "f02_ghz": table[:, 2].tolist(),
            }
        if plot_path is not None:
            _write_scqubits_plot(plot_path, execution, qubit_type)
            execution["plot_path"] = str(plot_path)
        return execution
    except Exception as error:  # pragma: no cover - depends on optional package details.
        return {"status": "failed", "error": f"{type(error).__name__}: {error}"}


def write_hamiltonian_model(
    sidecar: dict[str, Any],
    *,
    json_path: str | Path,
    script_path: str | Path,
    plot_path: str | Path | None = None,
    jc_ua_per_um2: float = 1.0,
    capacitance_ff: float | None = None,
    flux_bias_phi0: float = 0.0,
    squid_asymmetry: float = 0.0,
) -> dict[str, Any]:
    """Write a scqubits-ready Hamiltonian starter model from layout-derived JJ data."""
    output = Path(json_path)
    script = Path(script_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    script.parent.mkdir(parents=True, exist_ok=True)

    ideal = simulate_ideal_junction(
        sidecar,
        jc_ua_per_um2=jc_ua_per_um2,
        shunt_capacitance_ff=0.0,
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
    )
    ic_ua = float(ideal.get("critical_current_ua") or 0.0)
    ic_a = ic_ua * 1e-6
    ej_j = PHI0_WEBER * ic_a / (2.0 * math.pi) if ic_a > 0.0 else None
    ej_ghz = ej_j / PLANCK_J_S / 1e9 if ej_j is not None else None
    lj_ph = ideal.get("josephson_inductance_ph")
    center_ghz = _target_value(sidecar, "center_frequency_ghz", None, 5.0)
    if capacitance_ff is not None and capacitance_ff > 0.0:
        cap_ff = float(capacitance_ff)
    elif lj_ph is not None:
        cap_f = 1.0 / ((2.0 * math.pi * center_ghz * 1e9) ** 2 * float(lj_ph) * 1e-12)
        cap_ff = cap_f * 1e15
    else:
        cap_ff = None

    if cap_ff is not None and cap_ff > 0.0:
        ec_j = ELECTRON_CHARGE_C**2 / (2.0 * cap_ff * 1e-15)
        ec_ghz = ec_j / PLANCK_J_S / 1e9
    else:
        ec_ghz = None
    f01_ghz = (
        math.sqrt(8.0 * ej_ghz * ec_ghz) - ec_ghz
        if ej_ghz is not None and ec_ghz is not None
        else None
    )
    info = sidecar.get("info", {})
    uses_squid = bool(info.get("squid_enabled")) or int(info.get("squid_junction_count", 1)) > 1
    execution = _execute_scqubits(
        ej_ghz=ej_ghz,
        ec_ghz=ec_ghz,
        uses_squid=uses_squid,
        flux_bias_phi0=flux_bias_phi0,
        squid_asymmetry=squid_asymmetry,
        plot_path=Path(plot_path) if plot_path is not None else None,
    )
    model = {
        "schema": "text-to-gds.hamiltonian-model.v0",
        "integration": _integration("scqubits"),
        "source_gds": sidecar.get("gds_path"),
        "pcell": sidecar.get("pcell"),
        "model": "layout_derived_transmon_like_starter",
        "uses_squid": uses_squid,
        "parameters": {
            "junction_area_um2": ideal.get("junction_area_um2"),
            "jc_ua_per_um2": jc_ua_per_um2,
            "critical_current_ua": ic_ua,
            "josephson_inductance_ph": lj_ph,
            "capacitance_ff": cap_ff,
            "ej_ghz": ej_ghz,
            "ec_ghz": ec_ghz,
            "estimated_f01_ghz": f01_ghz,
            "estimated_anharmonicity_ghz": -ec_ghz if ec_ghz is not None else None,
            "flux_bias_phi0": flux_bias_phi0,
            "squid_asymmetry": squid_asymmetry,
        },
        "execution": execution,
        "model_validity": (
            "EJ/EC seeded from layout metadata, then diagonalized by scqubits when installed; "
            "use extracted capacitance and validated SQUID loop parameters before qubit signoff."
            if execution.get("status") == "executed"
            else "Starter Hamiltonian from layout metadata; use extracted capacitance and "
            "validated SQUID loop parameters before qubit signoff."
        ),
    }
    output.write_text(json.dumps(model, indent=2), encoding="utf-8")
    script.write_text(
        f'''# Text-to-GDS generated scqubits handoff.
from __future__ import annotations

import json
from pathlib import Path

MODEL_PATH = Path({json.dumps(str(output))})


def main() -> None:
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    params = model["parameters"]
    try:
        import scqubits as scq
    except ImportError as error:
        raise SystemExit(f"scqubits is not installed: {{error}}")
    if params["ej_ghz"] is None or params["ec_ghz"] is None:
        raise SystemExit("Need finite EJ and EC before creating a scqubits model.")
    qubit = scq.Transmon(
        EJ=params["ej_ghz"],
        EC=params["ec_ghz"],
        ng=0.0,
        ncut=31,
    )
    print(qubit.eigenvals(evals_count=5))


if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )
    model["script_path"] = str(script)
    model["json_path"] = str(output)
    output.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return model


def _execute_qiskit_metal(sidecar: dict[str, Any], *, gds_path: Path | None) -> dict[str, Any]:
    """Actually build a real Qiskit Metal QDesign + QComponent and render GDS when installed."""
    if find_spec("qiskit_metal") is None:
        return {
            "status": "skipped",
            "reason": (
                "qiskit_metal is not importable. On Windows/Python 3.12 it cannot be pip "
                "installed because PySide2 has no matching wheel; use conda or a Python "
                "<=3.10 environment, or install with: py -3 -m uv sync --extra metal."
            ),
        }
    try:
        import qiskit_metal as metal
        from qiskit_metal import designs
        from qiskit_metal.qlibrary.qubits.transmon_pocket import TransmonPocket

        design = designs.DesignPlanar()
        design.overwrite_enabled = True
        info = sidecar.get("info", {})
        pad_width_um = float(info.get("pad_width_um", 425.0))
        component = TransmonPocket(
            design,
            "Q_textlayout._legacy",
            options={"pad_width": f"{pad_width_um} um", "pocket_height": "650um"},
        )
        design.rebuild()
        tables = design.qgeometry.tables
        qgeometry_counts = {name: int(len(table)) for name, table in tables.items()}
        execution = {
            "status": "executed",
            "engine": f"qiskit-metal {getattr(metal, '__version__', 'unknown')}",
            "design_class": type(design).__name__,
            "component_class": type(component).__name__,
            "component_name": component.name,
            "qgeometry_counts": qgeometry_counts,
        }
        if gds_path is not None:
            gds_path.parent.mkdir(parents=True, exist_ok=True)
            gds_renderer = design.renderers.gds
            gds_renderer.export_to_gds(str(gds_path))
            execution["gds_path"] = str(gds_path)
            execution["gds_exists"] = gds_path.exists()
        return execution
    except Exception as error:  # pragma: no cover - depends on optional package details.
        return {"status": "failed", "error": f"{type(error).__name__}: {error}"}


def write_quantum_metal_bridge(
    sidecar: dict[str, Any],
    *,
    json_path: str | Path,
    script_path: str | Path,
    gds_path: str | Path | None = None,
    run: bool = True,
) -> dict[str, Any]:
    """Build a real Qiskit Metal design (when installed) plus the architecture-mapping bridge."""
    output = Path(json_path)
    script = Path(script_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    script.parent.mkdir(parents=True, exist_ok=True)

    execution = (
        _execute_qiskit_metal(sidecar, gds_path=Path(gds_path) if gds_path is not None else None)
        if run
        else {"status": "skipped", "reason": "run=False"}
    )
    bridge = {
        "schema": "text-to-gds.quantum-metal-bridge.v0",
        "integration": _integration("qiskit-metal"),
        "source_gds": sidecar.get("gds_path"),
        "component": {
            "name": sidecar.get("pcell"),
            "type": sidecar.get("info", {}).get("device_type", sidecar.get("pcell")),
            "options": sidecar.get("info", {}),
            "ports": _ports(sidecar),
        },
        "architecture_mapping": [
            {"textlayout._legacy": "PCell", "quantum_metal": "QComponent"},
            {"textlayout._legacy": "GDS layer polygons", "quantum_metal": "qgeometry tables"},
            {"textlayout._legacy": "export_* tools", "quantum_metal": "renderers"},
            {"textlayout._legacy": "run_simulation", "quantum_metal": "analyses/simulations"},
        ],
        "renderer_targets": ["GDS", "openEMS handoff", "JosephsonCircuits.jl handoff"],
        "execution": execution,
        "model_validity": (
            "Real Qiskit Metal QDesign/QComponent built and rendered to GDS."
            if execution.get("status") == "executed"
            else "Bridge metadata only; install qiskit-metal to instantiate a real QDesign."
        ),
    }
    output.write_text(json.dumps(bridge, indent=2), encoding="utf-8")
    script.write_text(
        f'''# Text-to-GDS generated Quantum Metal bridge skeleton.
from __future__ import annotations

import json
from pathlib import Path

BRIDGE_PATH = Path({json.dumps(str(output))})


def main() -> None:
    bridge = json.loads(BRIDGE_PATH.read_text(encoding="utf-8"))
    try:
        import qiskit_metal as metal
    except ImportError as error:
        raise SystemExit(f"Quantum Metal/Qiskit Metal is not installed: {{error}}")
    print(f"Loaded {{metal.__name__}} bridge for {{bridge['component']['name']}}")
    print("Create a QDesign/QComponent subclass here if round-trip import is required.")


if __name__ == "__main__":
    main()
''',
        encoding="utf-8",
    )
    bridge["script_path"] = str(script)
    bridge["json_path"] = str(output)
    output.write_text(json.dumps(bridge, indent=2), encoding="utf-8")
    return bridge


def _candidate_params(index: int, count: int, target_bandwidth_mhz: float) -> dict[str, float]:
    ratio = (index + 0.5) / max(count, 1)
    return {
        "jc_ua_per_um2": 0.5 + 4.5 * ratio,
        "flux_bias_phi0": min(0.48, 0.48 * ((index * 7) % max(count, 2)) / max(count - 1, 1)),
        "squid_asymmetry": 0.02 + 0.18 * ((index * 5 + 1) % max(count, 2)) / max(count - 1, 1),
        "pump_current_fraction": 0.006 + 0.044 * ((index * 3 + 2) % max(count, 2)) / max(count - 1, 1),
        "coupling_capacitance_ff": 5.0 + 95.0 * ((index * 11 + 3) % max(count, 2)) / max(
            count - 1,
            1,
        ),
        "target_bandwidth_mhz": max(
            50.0,
            target_bandwidth_mhz * (0.55 + 0.9 * ((index * 13 + 4) % max(count, 2)) / max(count - 1, 1)),
        ),
    }


def _evaluate_candidate(
    sidecar: dict[str, Any],
    params: dict[str, float],
    *,
    target_frequency_ghz: float,
    target_gain_db: float,
    target_bandwidth_mhz: float,
    min_p1db_dbm: float,
) -> dict[str, Any]:
    target_gain_estimate = target_gain_db + 18.0 * math.log10(
        max(params["pump_current_fraction"], 1e-9) / 0.017
    )
    target_gain_estimate -= 0.006 * abs(params["target_bandwidth_mhz"] - target_bandwidth_mhz)
    target_gain_estimate = max(0.0, min(35.0, target_gain_estimate))
    physical = estimate_physical_performance(
        sidecar,
        jc_ua_per_um2=params["jc_ua_per_um2"],
        shunt_capacitance_ff=0.0,
        target_frequency_ghz=target_frequency_ghz,
        target_gain_db=target_gain_estimate,
        target_bandwidth_mhz=params["target_bandwidth_mhz"],
        pump_current_fraction=params["pump_current_fraction"],
        coupling_capacitance_ff=params["coupling_capacitance_ff"],
        resonator_capacitance_ff=None,
        flux_bias_phi0=params["flux_bias_phi0"],
        squid_asymmetry=params["squid_asymmetry"],
        flux_sweep_span_phi0=1.0,
        flux_sweep_points=51,
        flux_period_current_ma=None,
        flux_mutual_inductance_ph=None,
    )
    flux = physical.get("flux_tuning") if isinstance(physical, dict) else None
    operating = flux.get("operating_point") if isinstance(flux, dict) else None
    center_ghz = (
        float(operating["resonant_frequency_ghz"])
        if isinstance(operating, dict) and operating.get("resonant_frequency_ghz") is not None
        else float(physical.get("center_frequency_ghz", target_frequency_ghz))
    )
    gain_db = float(physical.get("estimated_peak_gain_db", target_gain_estimate))
    bandwidth_mhz = float(physical.get("bandwidth_3db_mhz", params["target_bandwidth_mhz"]))
    p1db = float(physical.get("estimated_input_1db_compression_dbm", -120.0))
    objective = 0.0
    objective += max(target_gain_db - gain_db, 0.0) ** 2
    objective += (max(target_bandwidth_mhz - bandwidth_mhz, 0.0) / 100.0) ** 2
    objective += ((center_ghz - target_frequency_ghz) / 0.1) ** 2
    objective += max(min_p1db_dbm - p1db, 0.0) ** 2
    objective += 0.02 * max(gain_db - target_gain_db - 6.0, 0.0) ** 2
    return {
        "parameters": params,
        "metrics": {
            "center_frequency_ghz": center_ghz,
            "peak_gain_db": gain_db,
            "bandwidth_3db_mhz": bandwidth_mhz,
            "input_1db_compression_dbm": p1db,
            "critical_current_ua": physical.get("critical_current_ua"),
            "josephson_inductance_ph": physical.get("josephson_inductance_ph"),
            "pump_current_ua": physical.get("pump_current_ua"),
            "coupling_capacitance_ff": physical.get("coupling_capacitance_ff"),
        },
        "objective": objective,
    }


def _write_optimization_artifacts(
    *,
    rows: list[dict[str, Any]],
    csv_path: Path,
    plot_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "trial",
            "objective",
            "jc_ua_per_um2",
            "flux_bias_phi0",
            "squid_asymmetry",
            "pump_current_fraction",
            "coupling_capacitance_ff",
            "target_bandwidth_mhz",
            "center_frequency_ghz",
            "peak_gain_db",
            "bandwidth_3db_mhz",
            "input_1db_compression_dbm",
            "critical_current_ua",
            "josephson_inductance_ph",
            "pump_current_ua",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, row in enumerate(rows):
            writer.writerow(
                {
                    "trial": index,
                    "objective": row["objective"],
                    **row["parameters"],
                    **row["metrics"],
                }
            )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    trials = list(range(len(rows)))
    objective = [row["objective"] for row in rows]
    gain = [row["metrics"]["peak_gain_db"] for row in rows]
    bandwidth = [row["metrics"]["bandwidth_3db_mhz"] for row in rows]
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(3, 1, figsize=(8.6, 7.2), constrained_layout=True, sharex=True)
    axes[0].plot(trials, objective, marker="o", linewidth=1.6)
    axes[0].set_ylabel("objective")
    axes[1].plot(trials, gain, marker="o", linewidth=1.6, color="#34c759")
    axes[1].set_ylabel("gain (dB)")
    axes[2].plot(trials, bandwidth, marker="o", linewidth=1.6, color="#ff9f0a")
    axes[2].set_ylabel("BW (MHz)")
    axes[2].set_xlabel("trial")
    fig.suptitle("Text-to-GDS Research Optimization")
    fig.savefig(plot_path, dpi=220)
    plt.close(fig)


def run_research_optimization(
    sidecar: dict[str, Any],
    *,
    json_path: str | Path,
    csv_path: str | Path,
    plot_path: str | Path,
    n_trials: int = 16,
    target_frequency_ghz: float = 5.0,
    target_gain_db: float = 20.0,
    target_bandwidth_mhz: float = 500.0,
    min_p1db_dbm: float = -100.0,
    force_fallback: bool = False,
) -> dict[str, Any]:
    """Run Optuna when available, else a deterministic local grid search."""
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1, got {n_trials}")
    rows: list[dict[str, Any]] = []
    optuna_available = find_spec("optuna") is not None

    if optuna_available and not force_fallback:
        import optuna

        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(direction="minimize", sampler=sampler)

        def objective(trial: Any) -> float:
            params = {
                "jc_ua_per_um2": trial.suggest_float("jc_ua_per_um2", 0.5, 5.0),
                "flux_bias_phi0": trial.suggest_float("flux_bias_phi0", 0.0, 0.48),
                "squid_asymmetry": trial.suggest_float("squid_asymmetry", 0.0, 0.2),
                "pump_current_fraction": trial.suggest_float("pump_current_fraction", 0.006, 0.05),
                "coupling_capacitance_ff": trial.suggest_float(
                    "coupling_capacitance_ff",
                    5.0,
                    100.0,
                ),
                "target_bandwidth_mhz": trial.suggest_float(
                    "target_bandwidth_mhz",
                    0.5 * target_bandwidth_mhz,
                    1.5 * target_bandwidth_mhz,
                ),
            }
            row = _evaluate_candidate(
                sidecar,
                params,
                target_frequency_ghz=target_frequency_ghz,
                target_gain_db=target_gain_db,
                target_bandwidth_mhz=target_bandwidth_mhz,
                min_p1db_dbm=min_p1db_dbm,
            )
            trial.set_user_attr("row", row)
            return float(row["objective"])

        study.optimize(objective, n_trials=n_trials)
        rows = [trial.user_attrs["row"] for trial in study.trials if "row" in trial.user_attrs]
        engine = "optuna"
    else:
        for index in range(n_trials):
            rows.append(
                _evaluate_candidate(
                    sidecar,
                    _candidate_params(index, n_trials, target_bandwidth_mhz),
                    target_frequency_ghz=target_frequency_ghz,
                    target_gain_db=target_gain_db,
                    target_bandwidth_mhz=target_bandwidth_mhz,
                    min_p1db_dbm=min_p1db_dbm,
                )
            )
        engine = "fallback_grid"

    best = min(rows, key=lambda row: row["objective"])
    json_file = Path(json_path)
    csv_file = Path(csv_path)
    plot_file = Path(plot_path)
    _write_optimization_artifacts(rows=rows, csv_path=csv_file, plot_path=plot_file)
    result = {
        "schema": "text-to-gds.research-optimization.v0",
        "engine": engine,
        "integration": _integration("optuna"),
        "targets": {
            "center_frequency_ghz": target_frequency_ghz,
            "gain_db": target_gain_db,
            "bandwidth_3db_mhz": target_bandwidth_mhz,
            "minimum_input_1db_compression_dbm": min_p1db_dbm,
        },
        "best": best,
        "trials": rows,
        "result_path": str(json_file),
        "csv_path": str(csv_file),
        "plot_path": str(plot_file),
        "model_validity": (
            "Research optimizer uses layout-derived surrogate metrics unless wired to an "
            "external JosephsonCircuits/openEMS objective."
        ),
    }
    json_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
