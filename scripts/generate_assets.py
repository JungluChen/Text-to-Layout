"""Regenerate documentation assets from the strict physics-first workflow.

No performance curve is generated unless an external solver actually executes. When a
solver is unavailable, the corresponding asset is an explicit failure/status figure.

Run: uv run python scripts/generate_assets.py [layouts|sims|benchmarks|all]
"""

from __future__ import annotations

import json
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
WORKSPACE = ROOT / "workspace" / "artifacts"

_LAYOUTS: list[tuple[str, str, dict[str, Any], str]] = [
    ("manhattan_jj_layout", "manhattan_josephson_junction", {}, "manhattan_jj"),
    ("benchmark_01_manhattan_jj_layout", "manhattan_josephson_junction", {}, "benchmark_01"),
    (
        "benchmark_02_compact_cmos_logic_layout",
        "ground_plane",
        {"width": 5.0, "height": 5.0, "clearance": 1.0},
        "benchmark_02",
    ),
    (
        "benchmark_03_sfq_pulse_splitter_layout",
        "manhattan_josephson_junction",
        {
            "junction_width": 0.30,
            "junction_height": 0.30,
            "lead_width": 1.0,
            "lead_length": 4.0,
        },
        "benchmark_03",
    ),
    (
        "benchmark_04_jj_ic_calibration_array_layout",
        "jj_ic_calibration_array",
        {},
        "benchmark_04",
    ),
    (
        "benchmark_05_cpw_resonator_test_layout",
        "cpw_quarter_wave_resonator",
        # effective_permittivity is the CPW mode ε_eff (≈6.2 for Si substrate).
        # Do NOT pass ε_r=11.45 here — that is the bulk silicon dielectric constant.
        {"trace_width": 10.0, "gap": 6.0, "effective_permittivity": 6.2},
        "benchmark_05",
    ),
    (
        "benchmark_06_via_chain_monitor_layout",
        "via_chain_monitor",
        {"stage_count": 100},
        "benchmark_06",
    ),
]


def _copy(source: str | Path, asset_name: str) -> None:
    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, ASSETS / asset_name)
    print(f"  wrote assets/{asset_name} <- {source_path.name}")


def _relative(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _portable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_portable(item) for item in value]
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.is_absolute():
            return _relative(candidate)
    return value


def _failure(reason: str) -> dict[str, Any]:
    return {"status": "FAILED", "reason": reason}


def _strict_status(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"EXECUTED", "SUCCESS", "OK", "PASSED"}:
        return "EXECUTED"
    if normalized in {"SKIPPED", "SKIP"}:
        return "SKIPPED"
    return "FAILED"


def _intent_inputs(pcell: str, parameters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return explicit pre-layout requirements for each documentation example."""
    common = {"process": "documentation_example"}
    if pcell == "lumped_element_jpa_seed":
        return "Design a 6 GHz JPA with 20 dB gain and 200 MHz bandwidth", {
            **common,
            "device": "JPA",
            "frequency_ghz": 6.0,
            "gain_db": 20.0,
            "bandwidth_mhz": 200.0,
            "jc_ua_per_um2": 2.0,
            "junction_width_um": 0.22,
            "junction_height_um": 0.22,
            "junction_count": 2,
            "center_width_um": 10.0,
            "gap_um": 6.0,
            "ground_width_um": 500.0,
            "epsilon_r": 11.45,
            "substrate_thickness_um": 254.0,
            "impedance_tolerance_ohm": 5.0,
            "substrate": "high_resistivity_silicon",
            "package_clearance_um": 250.0,
            "wirebond_pads": True,
            "rf_ports": 2,
            "flux_line": True,
            "pump_frequency_ghz": 12.0,
            "pump_power_dbm": -130.0,
            "pump_mode": "flux",
        }
    if pcell == "cpw_quarter_wave_resonator":
        return "Design a 6 GHz CPW resonator with 10 MHz bandwidth", {
            **common,
            "device": "CPW_resonator",
            "frequency_ghz": 6.0,
            "bandwidth_mhz": 10.0,
            "center_width_um": float(parameters.get("trace_width", 10.0)),
            "gap_um": float(parameters.get("gap", 6.0)),
            "ground_width_um": float(parameters.get("ground_width", 500.0)),
            # epsilon_r is the substrate dielectric constant (silicon=11.45).
            # effective_permittivity (ε_eff≈6.2) is derived from ε_r by conformal mapping.
            "epsilon_r": 11.45,
            "substrate_thickness_um": float(parameters.get("substrate_thickness_um", 254.0)),
            "impedance_tolerance_ohm": 5.0,
            "substrate": str(parameters.get("substrate", "high_resistivity_silicon")),
            "package_clearance_um": 250.0,
            "wirebond_pads": True,
            "rf_ports": 2,
        }
    if pcell in {"manhattan_josephson_junction", "jj_ic_calibration_array"}:
        width = float(parameters.get("junction_width", 0.22))
        height = float(parameters.get("junction_height", 0.22))
        return "Generate a Josephson junction fabrication test structure", {
            **common,
            "device": "Josephson_junction",
            "jc_ua_per_um2": 2.0,
            "junction_width_um": width,
            "junction_height_um": height,
            "package_clearance_um": 250.0,
            "wirebond_pads": True,
            "dc_bias": True,
        }
    if pcell == "via_chain_monitor":
        return "Generate a via-chain process monitor", {
            **common,
            "device": "process_monitor",
            "package_clearance_um": 250.0,
            "wirebond_pads": True,
            "dc_bias": True,
        }
    return "Generate an isolated ground-plane process coupon", {
        **common,
        "device": "ground_plane",
    }


def _compile_with_intent(
    *, pcell: str, parameters: dict[str, Any], output_name: str
) -> dict[str, Any]:
    from text_to_gds.design_intent import synthesize_design_intent, write_design_intent
    from text_to_gds.server import compile_layout

    prompt, inputs = _intent_inputs(pcell, parameters)
    intent = synthesize_design_intent(prompt, inputs=inputs)
    if intent["status"] != "ready":
        raise RuntimeError(f"asset design intent failed for {pcell}: {intent['blockers']}")
    intent_path = WORKSPACE / f"{Path(output_name).stem}.design_intent.json"
    write_design_intent(intent, intent_path)
    print(f"  design_intent ready for {pcell}: {json.dumps(intent['blockers'])}")
    # compile_layout does not accept design_intent_path — store it alongside the output
    return compile_layout(
        pcell=pcell,
        parameters=parameters,
        output_name=output_name,
    )


def _eng_fmt(value: float, base_unit: str) -> str:
    """Engineering notation for extraction values."""
    if base_unit == "H":
        return f"{value*1e9:.4g} nH" if abs(value) >= 1e-9 else f"{value*1e12:.4g} pH"
    if base_unit == "F":
        return f"{value*1e12:.4g} pF" if abs(value) >= 1e-12 else f"{value*1e15:.4g} fF"
    if base_unit == "Hz":
        if abs(value) >= 1e9:
            return f"{value*1e-9:.4g} GHz"
        return f"{value*1e-6:.4g} MHz"
    if base_unit == "A":
        if abs(value) >= 1e-6:
            return f"{value*1e6:.4g} µA"
        return f"{value*1e9:.4g} nA"
    return f"{value:.4g} {base_unit}".rstrip()


def _render_status_figure(
    output_path: str | Path,
    *,
    title: str,
    extraction: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    layout_png: str | Path | None = None,
) -> Path:
    """Render geometry, extracted values, and solver status without inventing data.

    Column 3 shows a red FAILED panel when solver result is missing or failed.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.8), constrained_layout=True)
    fig.suptitle(title, fontsize=15, fontweight="bold")

    # --- Column 1: GDS geometry ---
    layout_file = Path(layout_png) if layout_png else None
    if layout_file and layout_file.is_file():
        axes[0].imshow(mpimg.imread(str(layout_file)))
        axes[0].axis("off")
        axes[0].set_title("GDS geometry")
    else:
        axes[0].text(0.5, 0.5, "Layout image\nunavailable", ha="center", va="center")
        axes[0].axis("off")
        axes[0].set_title("GDS geometry")

    # --- Column 2: Extracted values with lineage ---
    extraction = extraction if isinstance(extraction, dict) else {}
    params = extraction.get("parameters", {})

    lines: list[str] = [f"status: {extraction.get('status', '—')}"]
    area = params.get("junction_area_um2")
    if area is not None:
        lines.append(f"area:  {area:.4g} µm²")
    ic = params.get("critical_current_ua")
    if ic is not None:
        lines.append(f"Ic:    {ic:.4g} µA  [extracted]")
    lj = params.get("josephson_inductance_ph")
    if lj is not None:
        lines.append(f"Lj:    {lj:.4g} pH  [estimated]")
    f0 = params.get("resonant_frequency_ghz")
    if f0 is not None:
        lines.append(f"f0:    {f0:.4g} GHz [estimated]")
    bw = params.get("bandwidth_mhz")
    if bw is not None:
        lines.append(f"BW:    {bw:.4g} MHz")
    z0 = params.get("characteristic_impedance_ohm")
    if z0 is not None:
        lines.append(f"Z0:    {z0:.4g} Ω   [extracted]")
    if extraction.get("reason"):
        lines.append(f"\n{textwrap.fill(str(extraction['reason']), 38)}")

    axes[1].text(0.04, 0.97, "\n".join(lines) or "No extracted values",
                 va="top", family="monospace", fontsize=9, transform=axes[1].transAxes)
    axes[1].axis("off")
    axes[1].set_title("extraction.json")

    # --- Column 3: Solver evidence — red panel if failed/missing ---
    analysis = analysis if isinstance(analysis, dict) else _failure("solver result unavailable")
    status = _strict_status(analysis.get("status", "FAILED"))
    reason = textwrap.fill(str(analysis.get("reason") or analysis.get("error") or ""), 44)
    engine = analysis.get("engine") or analysis.get("adapter") or "not executed"

    if status in ("FAILED", "SKIPPED"):
        axes[2].set_facecolor("#ffdddd")
        label_color = "#cc0000"
        status_label = "SOLVER NOT EXECUTED" if status != "SKIPPED" else "SOLVER SKIPPED"
    else:
        axes[2].set_facecolor("#ddffdd")
        label_color = "#007700"
        status_label = "SOLVER EXECUTED"

    axes[2].text(
        0.5, 0.72, status_label,
        ha="center", va="center", fontsize=13, fontweight="bold", color=label_color,
        transform=axes[2].transAxes,
    )
    axes[2].text(
        0.5, 0.50, f"Engine: {engine}",
        ha="center", va="center", family="monospace", fontsize=9, color="#333333",
        transform=axes[2].transAxes,
    )
    if reason:
        axes[2].text(
            0.5, 0.30, reason,
            ha="center", va="center", family="monospace", fontsize=8, color="#555555",
            transform=axes[2].transAxes,
        )
    axes[2].axis("off")
    axes[2].set_title("Solver evidence")

    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    return output


def _render_openems_cpw_equations_asset(
    *,
    output_path: str | Path,
    compiled: dict[str, Any],
) -> Path:
    """Render the openEMS handoff using CPW quantities and microwave equations."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    from text_to_gds.automatic_mesh import generate_solver_inputs_from_graph
    from text_to_gds.physics_graph import extract_physics_graph

    sidecar = json.loads(Path(compiled["sidecar_path"]).read_text(encoding="utf-8"))
    graph = extract_physics_graph(
        compiled["gds_path"],
        sidecar,
        output_path=WORKSPACE / "asset_openems.physics_graph.json",
    )
    solver_inputs = generate_solver_inputs_from_graph(
        graph,
        output_dir=WORKSPACE / "asset_openems_solver_inputs",
    )
    cpw = next(node for node in graph["nodes"] if node["type"] == "transmission_line")
    params = cpw["physics_parameters"]
    z0 = params["z0"]["value"]
    eps_eff = params["epsilon_eff"]["value"]
    vp = params["phase_velocity"]["value"]
    c_per_m = params["capacitance_per_length"]["value"]
    l_per_m = params["inductance_per_length"]["value"]
    beta_rad_per_m = 2.0 * 3.141592653589793 * 6.0e9 / vp

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.8), constrained_layout=True)
    fig.suptitle("openEMS CPW handoff: geometry -> physics graph -> solver inputs", fontsize=14, fontweight="bold")

    axes[0].imshow(mpimg.imread(str(compiled["screenshot_path"])))
    axes[0].axis("off")
    axes[0].set_title("GDS geometry")

    equation_lines = [
        "Extracted CPW quantities",
        f"w = {params['width']['value']:.4g} um",
        f"g = {params['gap']['value']:.4g} um",
        f"l = {params['length']['value']:.4g} um",
        "",
        "Microwave equations",
        "Z0 = sqrt(L'/C')",
        "vp = 1/sqrt(L' C')",
        "epsilon_eff = (c/vp)^2",
        "beta = omega/vp",
        "",
        f"Z0 = {z0:.3f} ohm",
        f"epsilon_eff = {eps_eff:.4f}",
        f"L' = {l_per_m:.4e} H/m",
        f"C' = {c_per_m:.4e} F/m",
        f"vp = {vp:.4e} m/s",
        f"beta(6 GHz) = {beta_rad_per_m:.4e} rad/m",
    ]
    axes[1].text(0.03, 0.97, "\n".join(equation_lines), va="top", family="monospace", fontsize=8.5, transform=axes[1].transAxes)
    axes[1].axis("off")
    axes[1].set_title("physics_graph.json")

    files = solver_inputs["openems"]
    solver_lines = [
        "Generated openEMS inputs",
        f"geometry.xml: {Path(files['geometry_xml']).name}",
        f"mesh.xml:     {Path(files['mesh_xml']).name}",
        f"ports.xml:    {Path(files['ports_xml']).name}",
        "",
        "Mesh refinement",
    ]
    for rule in solver_inputs["mesh_refinement_rules"]:
        solver_lines.append(f"{rule['region']}: {rule['mesh_size_um']} um ({rule['priority']})")
    solver_lines.extend(
        [
            "",
            "Status: input files prepared",
            "No S-parameters are reported until",
            "openEMS produces a Touchstone file.",
        ]
    )
    axes[2].set_facecolor("#fff7d6")
    axes[2].text(0.03, 0.97, "\n".join(solver_lines), va="top", family="monospace", fontsize=8.5, transform=axes[2].transAxes)
    axes[2].axis("off")
    axes[2].set_title("solver contract")

    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)
    return output


def _extract(compiled: dict[str, Any]) -> dict[str, Any]:
    from text_to_gds.server import extract_layout
    return extract_layout(compiled["sidecar_path"])


def generate_layouts() -> None:
    """Generate layout-only figures directly from GDS geometry."""
    from text_to_gds.figures import render_publication_figure

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("Layout figures:")
    for asset_name, pcell, parameters, stem in _LAYOUTS:
        print(f"  [{stem}] compiling {pcell} ...")
        compiled = _compile_with_intent(
            pcell=pcell, parameters=parameters, output_name=f"{stem}.gds"
        )
        output_stem = WORKSPACE / stem
        publication = render_publication_figure(
            Path(compiled["gds_path"]),
            output_stem,
            sidecar_path=Path(compiled["sidecar_path"]),
            image_size=1200,
        )
        _copy(publication["png_path"], f"{asset_name}.png")


def generate_sims() -> None:
    """Generate solver assets or explicit failure figures when a solver is unavailable."""
    from text_to_gds.server import (
        export_hamiltonian_model,
        export_scientific_report,
        run_simulation,
    )

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("Simulation and lineage figures:")
    compiled = _compile_with_intent(
        pcell="lumped_element_jpa_seed",
        parameters={"center_frequency_ghz": 6.0},
        output_name="asset_seed.gds",
    )
    extraction = _extract(compiled)
    layout_png = compiled["screenshot_path"]

    # --- hfss_stack_3d: 3D stack view + extraction + solver status ---
    _render_status_figure(
        ASSETS / "hfss_stack_3d.png",
        title="Extracted GDS process stack — physics compiler",
        extraction=extraction,
        analysis=_failure("3D field solver not executed for this documentation asset"),
        layout_png=layout_png,
    )
    print("  wrote assets/hfss_stack_3d.png")

    # --- scqubits_spectrum_example: Hamiltonian handoff ---
    hamiltonian = export_hamiltonian_model(
        compiled["sidecar_path"],
        output_name="asset_scqubits",
        jc_ua_per_um2=2.0,
        flux_bias_phi0=0.25,
    )
    exec_block = hamiltonian.get("execution", {})
    hamiltonian_plot = exec_block.get("plot_path")
    if exec_block.get("status") == "executed" and hamiltonian_plot and Path(hamiltonian_plot).is_file():
        _copy(hamiltonian_plot, "scqubits_spectrum_example.png")
        print("  scqubits executed — real spectrum written")
    else:
        _render_status_figure(
            ASSETS / "scqubits_spectrum_example.png",
            title="scqubits Hamiltonian handoff (solver not available)",
            extraction=extraction,
            analysis={
                "status": "SKIPPED",
                "engine": "scqubits",
                "reason": exec_block.get("reason", "scqubits not installed or no energy levels returned"),
            },
            layout_png=layout_png,
        )
        print("  scqubits skipped — status figure written")

    # --- openems_extraction_example: CPW equations + generated solver inputs ---
    cpw_compiled = _compile_with_intent(
        pcell="cpw_quarter_wave_resonator",
        parameters={
            "target_frequency_ghz": 6.0,
            # ε_eff ≈ 6.2 for a CPW on silicon substrate (ε_r=11.45).
            # The parameter is the CPW mode effective permittivity, not ε_r.
            "effective_permittivity": 6.2,
            "trace_width": 10.0,
            "gap": 6.0,
        },
        output_name="asset_openems_cpw.gds",
    )
    _render_openems_cpw_equations_asset(
        output_path=ASSETS / "openems_extraction_example.png",
        compiled=cpw_compiled,
    )
    print("  wrote assets/openems_extraction_example.png")

    # --- jpa_analysis_example: JosephsonCircuits.jl simulation ---
    simulation = run_simulation(
        compiled["sidecar_path"],
        simulator="JosephsonCircuits.jl",
        jc_ua_per_um2=2.0,
        coupling_capacitance_ff=5.0,
    )
    adapter_ok = simulation.get("adapter_status") == "executed"
    sim_plot = simulation.get("scientific_plot_path")
    if adapter_ok and sim_plot and Path(sim_plot).is_file():
        _copy(sim_plot, "jpa_analysis_example.png")
        print("  JosephsonCircuits.jl executed — real JPA plot written")
    else:
        _render_status_figure(
            ASSETS / "jpa_analysis_example.png",
            title="JosephsonCircuits.jl harmonic balance (solver not executed)",
            extraction=extraction,
            analysis={
                "status": "FAILED",
                "engine": "JosephsonCircuits.jl",
                "reason": (
                    simulation.get("adapter_result", {}).get("reason")
                    or "Julia/JosephsonCircuits.jl runtime not available"
                ),
            },
            layout_png=layout_png,
        )
        print("  JosephsonCircuits.jl skipped — status figure written")

    # --- scientific_report_example: 10-panel composite ---
    report = export_scientific_report(
        compiled["sidecar_path"],
        gds_layout_png=layout_png,
        output_name="asset_report",
        jc_ua_per_um2=2.0,
        target_frequency_ghz=6.0,
        target_bandwidth_mhz=200.0,
    )
    report_png = report.get("png_path")
    if report_png and Path(report_png).is_file():
        _copy(report_png, "scientific_report_example.png")
        print("  scientific report written")
    else:
        _render_status_figure(
            ASSETS / "scientific_report_example.png",
            title="Scientific lineage report",
            extraction=extraction,
            analysis={"status": "FAILED", "reason": str(report.get("reason", "report generation failed"))},
            layout_png=layout_png,
        )
        print("  scientific report fallback written")


def _benchmark_inputs(pcell: str) -> dict[str, Any]:
    if pcell in {"manhattan_josephson_junction", "jj_ic_calibration_array"}:
        return {"jc_ua_per_um2": 2.0}
    return {}


def generate_benchmarks() -> None:
    """Generate benchmark figures: GDS, extraction.json, DRC, and real solver status."""
    from text_to_gds.server import run_drc, run_simulation

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("Physics-first benchmark figures:")
    entries = [
        (
            "benchmark_01_manhattan_jj_layout",
            "manhattan_josephson_junction",
            {"junction_width": 0.22, "junction_height": 0.22},
            "benchmark_01_sim",
        ),
        (
            "benchmark_02_compact_cmos_logic_layout",
            "ground_plane",
            {"width": 5.0, "height": 5.0, "clearance": 1.0},
            "benchmark_02_sim",
        ),
        (
            "benchmark_03_sfq_pulse_splitter_layout",
            "manhattan_josephson_junction",
            {
                "junction_width": 0.30,
                "junction_height": 0.30,
                "lead_width": 1.0,
                "lead_length": 4.0,
            },
            "benchmark_03_sim",
        ),
        (
            "benchmark_04_jj_ic_calibration_array_layout",
            "jj_ic_calibration_array",
            {},
            "benchmark_04_sim",
        ),
        (
            "benchmark_05_cpw_resonator_test_layout",
            "cpw_quarter_wave_resonator",
            {"trace_width": 10.0, "gap": 6.0, "effective_permittivity": 6.2},
            "benchmark_05_sim",
        ),
        (
            "benchmark_06_via_chain_monitor_layout",
            "via_chain_monitor",
            {"stage_count": 100},
            "benchmark_06_sim",
        ),
    ]

    for asset_name, pcell, parameters, stem in entries:
        print(f"  [{stem}] benchmark {pcell} ...")
        compiled = _compile_with_intent(
            pcell=pcell, parameters=parameters, output_name=f"{stem}.gds"
        )
        extraction = _extract(compiled)
        drc = run_drc(compiled["gds_path"], min_width_um=0.1)

        # Attempt real simulation only for JJ devices
        if pcell == "manhattan_josephson_junction":
            simulation = run_simulation(compiled["sidecar_path"], simulator="josim", jc_ua_per_um2=2.0)
            adapter_ok = simulation.get("adapter_status") == "executed"
            sim_analysis = {
                **simulation,
                "status": "EXECUTED" if adapter_ok else "FAILED",
                "engine": simulation.get("engine") or simulation.get("adapter") or "JoSIM",
            } if adapter_ok else {
                "status": "FAILED",
                "engine": "JoSIM",
                "reason": simulation.get("adapter_result", {}).get("reason") or "JoSIM not installed",
            }
        else:
            sim_analysis = _failure(f"no configured solver for benchmark: {pcell}")

        figure_path = _render_status_figure(
            WORKSPACE / f"{stem}.benchmark.png",
            title=f"Physics benchmark: {pcell}",
            extraction=extraction,
            analysis=sim_analysis,
            layout_png=compiled["screenshot_path"],
        )
        benchmark_asset = asset_name.replace("_layout", "_benchmark")
        _copy(figure_path, f"{benchmark_asset}.png")

        report = {
            "schema": "text-to-gds.asset-benchmark.v1",
            "device": pcell,
            "gds": _relative(compiled["gds_path"]),
            "extraction": {
                "path": _relative(extraction["result_path"]),
                "status": extraction.get("schema", "extracted"),
                "reason": extraction.get("reason"),
                "parameters": _portable(extraction.get("parameters", {})),
            },
            "drc": {
                "status": drc["status"],
                "checked_shapes": drc.get("checked_shapes", 0),
            },
            "simulation": {
                "status": _strict_status(sim_analysis.get("status")),
                "reason": sim_analysis.get("reason"),
                "engine": sim_analysis.get("engine"),
            },
        }
        report_path = WORKSPACE / f"{stem}.report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    selected = sys.argv[1] if len(sys.argv) > 1 else "all"
    if selected not in {"layouts", "sims", "benchmarks", "all"}:
        raise SystemExit("usage: generate_assets.py [layouts|sims|benchmarks|all]")
    if selected in {"layouts", "all"}:
        generate_layouts()
    if selected in {"sims", "all"}:
        generate_sims()
    if selected in {"benchmarks", "all"}:
        generate_benchmarks()
    print("Done.")


if __name__ == "__main__":
    main()
