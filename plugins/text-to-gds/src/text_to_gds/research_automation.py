"""EM setup, circuit synthesis, quantum dynamics, experiment automation, and research agents."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Any, Callable

import numpy as np

from text_to_gds.physics_extensions import LIGHT_SPEED

BOLTZMANN = 1.380649e-23
PLANCK = 6.62607015e-34


def automatic_port_placement(sidecar: dict[str, Any]) -> list[dict[str, Any]]:
    ports = sidecar.get("ports", [])
    if ports:
        return [{**port, "source": "semantic_port"} for port in ports]
    bbox = sidecar.get("bbox_um") or [0.0, 0.0, 100.0, 100.0]
    if isinstance(bbox[0], list):
        bbox = [bbox[0][0], bbox[0][1], bbox[1][0], bbox[1][1]]
    xmin, ymin, xmax, ymax = map(float, bbox)
    return [
        {"name": "input", "center": [xmin, (ymin + ymax) / 2.0], "orientation": 180.0, "source": "bbox_edge"},
        {"name": "output", "center": [xmax, (ymin + ymax) / 2.0], "orientation": 0.0, "source": "bbox_edge"},
    ]


def select_boundary_conditions(*, solver: str, geometry_class: str, eigenmode: bool = False) -> dict[str, Any]:
    if eigenmode:
        boundary = "perfect_electric_conductor_package"
    elif geometry_class == "planar":
        boundary = "open_pml_or_radiation"
    elif geometry_class == "volumetric":
        boundary = "radiation_with_conductor_walls"
    else:
        boundary = "open"
    return {"solver": solver, "boundary": boundary, "ports": "wave" if solver.lower() == "hfss" else "lumped", "requires_review": True}


def size_radiation_box(*, device_bbox_um: list[float], maximum_frequency_ghz: float, epsilon_r: float = 1.0, wavelength_fraction: float = 0.25) -> dict[str, Any]:
    if min(maximum_frequency_ghz, epsilon_r, wavelength_fraction) <= 0.0:
        raise ValueError("Radiation-box inputs must be positive")
    margin_um = LIGHT_SPEED / (maximum_frequency_ghz * 1e9 * math.sqrt(epsilon_r)) * wavelength_fraction * 1e6
    xmin, ymin, xmax, ymax = device_bbox_um
    return {"margin_um": margin_um, "bbox_um": [xmin - margin_um, ymin - margin_um, -margin_um, xmax + margin_um, ymax + margin_um, margin_um]}


def mesh_quality_score(elements: list[dict[str, float]]) -> dict[str, Any]:
    if not elements:
        raise ValueError("Mesh elements are required")
    scores = []
    for element in elements:
        aspect = max(float(element["aspect_ratio"]), 1.0)
        skew = max(float(element.get("skewness", 0.0)), 0.0)
        jacobian = max(min(float(element.get("jacobian", 1.0)), 1.0), 0.0)
        scores.append(max(0.0, min(1.0, (1.0 / aspect) * (1.0 - min(skew, 1.0)) * jacobian)))
    return {"score": float(np.mean(scores)), "minimum": float(np.min(scores)), "poor_element_fraction": float(np.mean(np.asarray(scores) < 0.2)), "element_count": len(scores)}


def convergence_checker(history: list[dict[str, float]], *, metric: str, tolerance_fraction: float = 1e-3, required_consecutive: int = 2) -> dict[str, Any]:
    values = np.asarray([row[metric] for row in history], dtype=float)
    if values.size < required_consecutive + 1:
        return {"converged": False, "reason": "insufficient iterations"}
    changes = np.abs(np.diff(values) / np.maximum(np.abs(values[1:]), 1e-30))
    return {"converged": bool(np.all(changes[-required_consecutive:] <= tolerance_fraction)), "relative_changes": changes.tolist(), "last_value": float(values[-1])}


def estimate_simulation_cost(*, cells: int, frequency_points: int, solver: str, cores: int = 1) -> dict[str, float]:
    if min(cells, frequency_points, cores) < 1:
        raise ValueError("Simulation size and cores must be positive")
    exponent = 1.35 if solver.lower() in {"hfss", "palace", "elmer"} else 1.1
    core_hours = (cells / 1e6) ** exponent * max(frequency_points, 1) / max(cores**0.75, 1.0)
    memory_gb = 2.0 + 0.000004 * cells
    return {"estimated_core_hours": core_hours, "estimated_wall_hours": core_hours / cores, "estimated_memory_gb": memory_gb}


def multi_solver_report(results: list[dict[str, Any]], metrics: list[str]) -> dict[str, Any]:
    rows = []
    for result in results:
        rows.append({"solver": result["solver"], **{metric: result.get(metric) for metric in metrics}, "status": result.get("status", "unknown")})
    spread = {}
    for metric in metrics:
        values = [float(row[metric]) for row in rows if row[metric] is not None]
        spread[metric] = {"minimum": min(values), "maximum": max(values), "relative_spread": (max(values) - min(values)) / max(abs(np.mean(values)), 1e-30)} if values else None
    return {"schema": "text-to-gds.multi-solver-report.v1", "results": rows, "spread": spread}


def train_em_surrogate(samples: list[dict[str, Any]], parameter_names: list[str], metric_names: list[str], *, ridge: float = 1e-8) -> dict[str, Any]:
    """Train a standardized quadratic ridge surrogate with deterministic coefficients."""
    x = np.asarray([[float(row["parameters"][name]) for name in parameter_names] for row in samples])
    y = np.asarray([[float(row["metrics"][name]) for name in metric_names] for row in samples])
    mean, scale = np.mean(x, axis=0), np.maximum(np.std(x, axis=0), 1e-12)
    z = (x - mean) / scale
    features = np.column_stack([np.ones(len(z)), z, z**2])
    coefficients = np.linalg.solve(features.T @ features + ridge * np.eye(features.shape[1]), features.T @ y)
    predicted = features @ coefficients
    return {"schema": "text-to-gds.em-surrogate.v1", "parameter_names": parameter_names, "metric_names": metric_names, "mean": mean.tolist(), "scale": scale.tolist(), "coefficients": coefficients.tolist(), "training_rms": np.sqrt(np.mean((predicted - y) ** 2, axis=0)).tolist(), "model": "quadratic_ridge"}


def predict_em_surrogate(model: dict[str, Any], parameters: dict[str, float]) -> dict[str, float]:
    x = np.asarray([parameters[name] for name in model["parameter_names"]])
    z = (x - np.asarray(model["mean"])) / np.asarray(model["scale"])
    features = np.r_[1.0, z, z**2]
    prediction = features @ np.asarray(model["coefficients"])
    return dict(zip(model["metric_names"], prediction.tolist(), strict=True))


def recognize_circuit_topology(circuit: dict[str, Any]) -> dict[str, Any]:
    kinds = [element.get("kind") for element in circuit.get("elements", [])]
    degrees: dict[str, int] = {}
    for element in circuit.get("elements", []):
        for node in element.get("nodes", []):
            degrees[node] = degrees.get(node, 0) + 1
    if kinds.count("josephson_junction") == 2:
        topology = "dc_squid_or_jpa"
    elif "transmission_line" in kinds and kinds.count("josephson_junction") > 10:
        topology = "jtwpa"
    elif kinds.count("capacitor") >= 2 and kinds.count("inductor") >= 1:
        topology = "filter_or_resonator"
    else:
        topology = "generic_network"
    return {"topology": topology, "device_counts": {kind: kinds.count(kind) for kind in sorted(set(kinds))}, "node_degrees": degrees}


def circuit_graph_features(circuit: dict[str, Any]) -> dict[str, Any]:
    nodes = circuit.get("nodes", [])
    index = {node: position for position, node in enumerate(nodes)}
    adjacency = np.zeros((len(nodes), len(nodes)), dtype=int)
    features = []
    vocabulary = ["resistor", "capacitor", "inductor", "josephson_junction", "transmission_line"]
    for element in circuit.get("elements", []):
        connected = element.get("nodes", [])
        if len(connected) >= 2 and connected[0] in index and connected[1] in index:
            adjacency[index[connected[0]], index[connected[1]]] += 1
            adjacency[index[connected[1]], index[connected[0]]] += 1
        features.append([1 if element.get("kind") == kind else 0 for kind in vocabulary])
    return {"nodes": nodes, "adjacency": adjacency.tolist(), "element_features": features, "feature_names": vocabulary, "gnn_ready": True}


def parasitic_aware_netlist(circuit: dict[str, Any], *, capacitance_per_node_f: float = 1e-15, series_inductance_h: float = 10e-12) -> dict[str, Any]:
    elements = list(circuit.get("elements", []))
    for node in circuit.get("nodes", []):
        if node != "0":
            elements.append({"name": f"CP_{node}", "kind": "capacitor", "nodes": [node, "0"], "parameters": {"capacitance_f": capacitance_per_node_f}})
    for index, port in enumerate(circuit.get("ports", [])):
        elements.append({"name": f"LP{index + 1}", "kind": "inductor", "nodes": [port, f"{port}_EXT"], "parameters": {"inductance_h": series_inductance_h}})
    return {**circuit, "schema": "text-to-gds.parasitic-circuit.v1", "elements": elements, "parasitic_model": "node_shunt_C_and_port_series_L"}


def extract_distributed_circuit(*, length_um: float, sections: int, inductance_h_per_m: float, capacitance_f_per_m: float, resistance_ohm_per_m: float = 0.0) -> dict[str, Any]:
    if length_um <= 0.0 or sections < 1:
        raise ValueError("Positive length and sections are required")
    length = length_um * 1e-6 / sections
    elements = []
    for index in range(sections):
        left, right = f"N{index}", f"N{index + 1}"
        elements.extend([
            {"name": f"R{index + 1}", "kind": "resistor", "nodes": [left, right], "parameters": {"resistance_ohm": resistance_ohm_per_m * length}},
            {"name": f"L{index + 1}", "kind": "inductor", "nodes": [left, right], "parameters": {"inductance_h": inductance_h_per_m * length}},
            {"name": f"C{index + 1}", "kind": "capacitor", "nodes": [right, "0"], "parameters": {"capacitance_f": capacitance_f_per_m * length}},
        ])
    return {"schema": "text-to-gds.distributed-circuit.v1", "nodes": [f"N{index}" for index in range(sections + 1)] + ["0"], "elements": elements}


def synthesize_filter(*, kind: str, order: int, cutoff_hz: float, impedance_ohm: float = 50.0) -> dict[str, Any]:
    if kind not in {"butterworth_lowpass", "butterworth_highpass"} or order < 1 or min(cutoff_hz, impedance_ohm) <= 0.0:
        raise ValueError("Invalid filter specification")
    omega = 2.0 * math.pi * cutoff_hz
    elements = []
    for index in range(1, order + 1):
        g = 2.0 * math.sin((2 * index - 1) * math.pi / (2 * order))
        series = (index % 2 == 1) == (kind == "butterworth_lowpass")
        if series:
            elements.append({"kind": "inductor", "value_h": impedance_ohm * g / omega})
        else:
            elements.append({"kind": "capacitor", "value_f": g / (impedance_ohm * omega)})
    return {"kind": kind, "order": order, "elements": elements}


def synthesize_matching_network(*, source_ohm: float, load_ohm: float, frequency_hz: float, topology: str = "lowpass") -> dict[str, float | str]:
    if min(source_ohm, load_ohm, frequency_hz) <= 0.0 or source_ohm == load_ohm:
        raise ValueError("Positive unequal impedances are required")
    high, low = max(source_ohm, load_ohm), min(source_ohm, load_ohm)
    q = math.sqrt(high / low - 1.0)
    omega = 2.0 * math.pi * frequency_hz
    series_x = q * low
    shunt_x = high / q
    return {"topology": topology, "series_inductance_h": series_x / omega, "shunt_capacitance_f": 1.0 / (omega * shunt_x), "loaded_q": q}


def synthesize_transformer(*, source_ohm: float, load_ohm: float, frequency_hz: float, velocity_m_per_s: float) -> dict[str, float]:
    return {"characteristic_impedance_ohm": math.sqrt(source_ohm * load_ohm), "quarter_wave_length_m": velocity_m_per_s / (4.0 * frequency_hz), "turns_ratio": math.sqrt(load_ohm / source_ohm)}


def optimize_smith_chart(candidates: list[dict[str, Any]], *, target_impedance: complex = 50 + 0j) -> dict[str, Any]:
    if not candidates:
        raise ValueError("Candidates are required")
    scored = []
    for candidate in candidates:
        impedance = complex(*candidate["impedance_ohm"]) if isinstance(candidate["impedance_ohm"], list) else complex(candidate["impedance_ohm"])
        gamma = (impedance - target_impedance) / (impedance + target_impedance)
        scored.append((abs(gamma), candidate, gamma))
    magnitude, selected, gamma = min(scored, key=lambda item: item[0])
    return {"selected": selected, "reflection_magnitude": magnitude, "reflection": [gamma.real, gamma.imag], "return_loss_db": -20.0 * math.log10(max(magnitude, 1e-15))}


def pump_heating(*, pump_power_dbm: list[float], absorption_fraction: float, thermal_conductance_w_per_k: float, base_temperature_k: float) -> dict[str, Any]:
    if not 0.0 <= absorption_fraction <= 1.0 or thermal_conductance_w_per_k <= 0.0:
        raise ValueError("Invalid heating parameters")
    temperatures = []
    for power in pump_power_dbm:
        absorbed = 1e-3 * 10.0 ** (power / 10.0) * absorption_fraction
        temperatures.append(base_temperature_k + absorbed / thermal_conductance_w_per_k)
    return {"pump_power_dbm": pump_power_dbm, "device_temperature_k": temperatures}


def pump_induced_shift(*, photon_numbers: list[float], kerr_hz_per_photon: float, stark_coefficient_hz_per_photon: float = 0.0) -> dict[str, Any]:
    coefficient = kerr_hz_per_photon + stark_coefficient_hz_per_photon
    return {"photon_number": photon_numbers, "frequency_shift_hz": [coefficient * value for value in photon_numbers], "kerr_component_hz": [kerr_hz_per_photon * value for value in photon_numbers], "stark_component_hz": [stark_coefficient_hz_per_photon * value for value in photon_numbers]}


def extract_kerr(photon_numbers: list[float], frequency_hz: list[float]) -> dict[str, float]:
    photons, frequency = np.asarray(photon_numbers), np.asarray(frequency_hz)
    slope, intercept = np.polyfit(photons, frequency, 1)
    residual = frequency - (slope * photons + intercept)
    return {"kerr_hz_per_photon": float(slope), "zero_photon_frequency_hz": float(intercept), "rms_error_hz": float(np.sqrt(np.mean(residual**2)))}


def bifurcation_boundary(*, detuning_hz: list[float], damping_hz: float, kerr_hz: float) -> dict[str, Any]:
    if damping_hz <= 0.0 or kerr_hz == 0.0:
        raise ValueError("Damping must be positive and Kerr non-zero")
    rows = []
    for detuning in detuning_hz:
        discriminant = detuning**2 - 3.0 * (damping_hz / 2.0) ** 2
        critical_photons = max((-2.0 * detuning + math.sqrt(max(discriminant, 0.0))) / (3.0 * kerr_hz), 0.0) if discriminant >= 0 else math.nan
        rows.append({"detuning_hz": detuning, "critical_photons": critical_photons, "bistable_possible": discriminant >= 0})
    return {"boundary": rows}


def parameter_sensitivity(values: list[float], metric: list[float], *, noise_sigma: float = 0.0) -> dict[str, float]:
    x, y = np.asarray(values), np.asarray(metric)
    slope = float(np.polyfit(x, y, 1)[0])
    return {"sensitivity": slope, "predicted_metric_sigma": abs(slope) * noise_sigma}


def saturation_mechanism_analysis(evidence: dict[str, float]) -> dict[str, Any]:
    candidates = {
        "pump_depletion": float(evidence.get("pump_depletion_fraction", 0.0)),
        "kerr_detuning": abs(float(evidence.get("kerr_shift_over_bandwidth", 0.0))),
        "junction_current": float(evidence.get("current_over_critical", 0.0)),
        "heating": float(evidence.get("temperature_over_critical", 0.0)),
    }
    return {"dominant_mechanism": max(candidates, key=candidates.get), "scores": candidates}


def design_twpa_unit_cell(*, target_impedance_ohm: float, cutoff_frequency_ghz: float, cell_length_um: float) -> dict[str, float]:
    omega = 2.0 * math.pi * cutoff_frequency_ghz * 1e9
    inductance = target_impedance_ohm / omega
    capacitance = 1.0 / (target_impedance_ohm * omega)
    return {"series_inductance_h": inductance, "shunt_capacitance_f": capacitance, "cell_length_um": cell_length_um, "phase_velocity_m_per_s": cell_length_um * 1e-6 / math.sqrt(inductance * capacitance)}


def artificial_transmission_line(*, cells: int, unit_cell: dict[str, float]) -> dict[str, Any]:
    return {"cells": cells, "total_inductance_h": cells * unit_cell["series_inductance_h"], "total_capacitance_f": cells * unit_cell["shunt_capacitance_f"], "length_um": cells * unit_cell["cell_length_um"], "unit_cell": unit_cell}


def photonic_crystal_profile(*, cells: int, period_cells: int, modulation_fraction: float, base_value: float) -> list[float]:
    if cells < 1 or period_cells < 2 or abs(modulation_fraction) >= 1.0:
        raise ValueError("Invalid photonic crystal parameters")
    return [base_value * (1.0 + modulation_fraction * math.cos(2.0 * math.pi * index / period_cells)) for index in range(cells)]


def optimize_stopband(candidates: list[dict[str, float]], *, target_center_ghz: float, target_width_ghz: float) -> dict[str, Any]:
    return min(candidates, key=lambda row: abs(row["center_ghz"] - target_center_ghz) / target_center_ghz + abs(row["width_ghz"] - target_width_ghz) / target_width_ghz)


def optimize_broadband_gain(candidates: list[dict[str, Any]], *, minimum_gain_db: float) -> dict[str, Any]:
    scored = []
    for candidate in candidates:
        gain = np.asarray(candidate["gain_db"])
        passing = gain >= minimum_gain_db
        score = float(np.mean(passing)) - 0.01 * float(np.ptp(gain[passing])) if np.any(passing) else -math.inf
        scored.append((score, candidate))
    score, selected = max(scored, key=lambda item: item[0])
    return {"selected": selected, "score": score}


def lindblad_evolution(*, hamiltonian: list[list[complex]], collapse_operators: list[list[list[complex]]], initial_density: list[list[complex]], times_s: list[float]) -> dict[str, Any]:
    """Integrate the Lindblad master equation with RK4."""
    h = np.asarray(hamiltonian, dtype=complex)
    collapse = [np.asarray(operator, dtype=complex) for operator in collapse_operators]
    rho = np.asarray(initial_density, dtype=complex)

    def derivative(state: np.ndarray) -> np.ndarray:
        value = -1j * (h @ state - state @ h) / (PLANCK / (2.0 * math.pi))
        for operator in collapse:
            product = operator.conj().T @ operator
            value += operator @ state @ operator.conj().T - 0.5 * (product @ state + state @ product)
        return value

    states = [rho.copy()]
    for left, right in zip(times_s, times_s[1:]):
        dt = right - left
        k1 = derivative(rho)
        k2 = derivative(rho + dt * k1 / 2.0)
        k3 = derivative(rho + dt * k2 / 2.0)
        k4 = derivative(rho + dt * k3)
        rho = rho + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        rho = (rho + rho.conj().T) / 2.0
        rho /= np.trace(rho)
        states.append(rho.copy())
    def encode(matrix: np.ndarray) -> list[list[list[float]]]:
        return [[[float(value.real), float(value.imag)] for value in row] for row in matrix]
    return {"schema": "text-to-gds.lindblad.v1", "times_s": times_s, "density_matrices": [encode(state) for state in states], "trace_error": float(abs(np.trace(rho) - 1.0))}


def qutip_backend() -> dict[str, Any]:
    try:
        import qutip

        return {"available": True, "version": qutip.__version__, "backend": "qutip.mesolve"}
    except ImportError:
        return {"available": False, "backend": "internal_rk4_lindblad", "install_hint": "uv add qutip"}


def decoherence_model(*, relaxation_s: float, pure_dephasing_s: float) -> dict[str, float]:
    if min(relaxation_s, pure_dephasing_s) <= 0.0:
        raise ValueError("Decoherence times must be positive")
    t2 = 1.0 / (1.0 / (2.0 * relaxation_s) + 1.0 / pure_dephasing_s)
    return {"t1_s": relaxation_s, "t_phi_s": pure_dephasing_s, "t2_s": t2, "relaxation_rate_hz": 1.0 / relaxation_s, "dephasing_rate_hz": 1.0 / pure_dephasing_s}


def thermal_photon_analysis(*, frequency_hz: float, temperature_k: float) -> dict[str, float]:
    occupation = 1.0 / math.expm1(PLANCK * frequency_hz / (BOLTZMANN * temperature_k))
    return {"mean_photon_number": occupation, "excited_state_fraction": occupation / (1.0 + 2.0 * occupation)}


def propagate_quantum_noise(stages: list[dict[str, float]], *, input_photons: float = 0.5) -> dict[str, Any]:
    photons = input_photons
    rows = []
    total_gain = 1.0
    for stage in stages:
        gain = 10.0 ** (stage.get("gain_db", 0.0) / 10.0)
        photons = gain * photons + float(stage.get("added_noise_photons", 0.0))
        total_gain *= gain
        rows.append({"name": stage.get("name", f"stage_{len(rows)}"), "output_photons": photons})
    return {"output_photons": photons, "input_referred_added_photons": photons / total_gain - input_photons, "stages": rows}


def reconstruct_quantum_state(i_samples: list[float], q_samples: list[float], *, cutoff: int = 8) -> dict[str, Any]:
    i, q = np.asarray(i_samples), np.asarray(q_samples)
    alpha = i + 1j * q
    mean_n = float(np.mean(np.abs(alpha) ** 2))
    probabilities = np.asarray([math.exp(-mean_n) * mean_n**n / math.factorial(n) for n in range(cutoff)])
    probabilities /= np.sum(probabilities)
    return {"method": "coherent-state moment reconstruction", "mean_photon_number": mean_n, "fock_probabilities": probabilities.tolist(), "density_matrix_diagonal": probabilities.tolist()}


def squeezing_tomography(phases_deg: list[float], quadrature_samples: list[list[float]]) -> dict[str, Any]:
    if len(phases_deg) != len(quadrature_samples):
        raise ValueError("Phase and quadrature sweep lengths must match")
    variances = [float(np.var(samples, ddof=1)) for samples in quadrature_samples]
    minimum = int(np.argmin(variances))
    return {"phases_deg": phases_deg, "variances": variances, "squeezed_phase_deg": phases_deg[minimum], "minimum_variance": variances[minimum]}


def cooldown_tracking(readings: list[dict[str, float]], *, target_temperature_k: float) -> dict[str, Any]:
    temperatures = np.asarray([row["temperature_k"] for row in readings])
    timestamps = np.asarray([row["time_s"] for row in readings])
    slope = float(np.polyfit(timestamps[-min(len(timestamps), 10) :], temperatures[-min(len(temperatures), 10) :], 1)[0]) if len(readings) >= 2 else math.nan
    return {"latest_temperature_k": float(temperatures[-1]), "target_reached": bool(temperatures[-1] <= target_temperature_k), "recent_cooling_rate_k_per_s": slope}


def fridge_monitor(readings: dict[str, float], limits: dict[str, tuple[float, float]]) -> dict[str, Any]:
    alarms = [{"channel": name, "value": readings.get(name), "limits": list(bounds)} for name, bounds in limits.items() if name not in readings or not bounds[0] <= readings[name] <= bounds[1]]
    return {"healthy": not alarms, "alarms": alarms, "readings": readings}


def schedule_experiments(experiments: list[dict[str, Any]], *, start: str | None = None) -> dict[str, Any]:
    current = datetime.fromisoformat(start) if start else datetime.now()
    rows = []
    for experiment in sorted(experiments, key=lambda item: (-int(item.get("priority", 0)), item["name"])):
        finish = current + timedelta(seconds=float(experiment["duration_s"]))
        rows.append({**experiment, "start": current.isoformat(), "finish": finish.isoformat()})
        current = finish
    return {"schedule": rows, "completion": current.isoformat()}


def overnight_agent(schedule: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("fridge_healthy", False) or not state.get("instruments_healthy", False):
        return {"status": "blocked_by_safety_interlock", "next_experiment": None}
    pending = [row for row in schedule.get("schedule", []) if row.get("status", "pending") == "pending"]
    return {"status": "ready" if pending else "complete", "next_experiment": pending[0] if pending else None}


def automatic_parameter_search(bounds: dict[str, tuple[float, float]], objective: Callable[[dict[str, float]], float], *, samples: int = 100, seed: int = 42) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    best = None
    history = []
    for _ in range(samples):
        point = {name: float(rng.uniform(low, high)) for name, (low, high) in bounds.items()}
        score = float(objective(point))
        history.append({"parameters": point, "score": score})
        if best is None or score > best["score"]:
            best = history[-1]
    return {"best": best, "history": history}


def measurement_anomaly_detection(values: list[float], *, window: int = 20, z_threshold: float = 5.0) -> dict[str, Any]:
    data = np.asarray(values, dtype=float)
    anomalies = []
    for index in range(window, len(data)):
        baseline = data[index - window : index]
        median = np.median(baseline)
        sigma = max(np.median(np.abs(baseline - median)) * 1.4826, 1e-30)
        if abs(data[index] - median) / sigma > z_threshold:
            anomalies.append(index)
    return {"anomaly_indices": anomalies, "stop_recommended": bool(anomalies and anomalies[-1] == len(data) - 1)}


def measurement_stop_condition(state: dict[str, Any], conditions: dict[str, Any]) -> dict[str, Any]:
    triggered = []
    for key, limit in conditions.items():
        value = state.get(key)
        if isinstance(limit, dict):
            if value is None or value < limit.get("minimum", -math.inf) or value > limit.get("maximum", math.inf):
                triggered.append(key)
        elif value == limit:
            triggered.append(key)
    return {"stop": bool(triggered), "triggered": triggered}


def instrument_health(status: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [item for item in status if not item.get("responding") or item.get("error_queue") not in (None, "0", "+0,\"No error\"")]
    return {"healthy": not failed, "failed": failed, "instrument_count": len(status)}


def remote_experiment_command(command: str, parameters: dict[str, Any], *, authenticated: bool, dry_run: bool = True) -> dict[str, Any]:
    allowed = {"status", "start_approved_recipe", "stop", "pause"}
    if not authenticated:
        raise PermissionError("Remote experiment control requires authentication")
    if command not in allowed:
        raise ValueError("Remote command is not allowlisted")
    return {"command": command, "parameters": parameters, "status": "validated_dry_run" if dry_run else "ready_for_local_controller", "hardware_touched": False}


def paper_reading_agent(text: str) -> dict[str, Any]:
    sections = re.split(r"\n(?=[A-Z][A-Za-z ]{2,40}\n)", text)
    numbers = re.findall(r"\b\d+(?:\.\d+)?\s*(?:GHz|MHz|dB|mK|K|nm|um|µm)\b", text)
    return {"section_count": len(sections), "reported_values": numbers, "summary": " ".join(re.split(r"(?<=[.!?])\s+", text.strip())[:5]), "requires_source_verification": True}


def equation_extraction_agent(text: str) -> dict[str, Any]:
    latex = re.findall(r"\$\$(.+?)\$\$|\$(.+?)\$", text, re.DOTALL)
    assignments = re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^,;.\n]+)", text)
    return {"latex": [left or right for left, right in latex], "assignments": [{"symbol": symbol, "expression": expression.strip()} for symbol, expression in assignments]}


def simulation_reproduction_agent(paper: dict[str, Any], available_backends: list[str]) -> dict[str, Any]:
    required = paper.get("required_backend", "analytical")
    return {"status": "ready" if required in available_backends or required == "analytical" else "blocked_missing_backend", "required_backend": required, "parameters": paper.get("parameters", {}), "comparison_metrics": paper.get("reported", {})}


def reviewer_criticism_agent(work: dict[str, Any]) -> dict[str, Any]:
    checks = {"calibration": bool(work.get("calibration")), "uncertainty": bool(work.get("uncertainty")), "independent_validation": bool(work.get("independent_validation")), "raw_data": bool(work.get("raw_data")), "limitations": bool(work.get("limitations"))}
    return {"criticisms": [f"Missing {name.replace('_', ' ')} evidence." for name, present in checks.items() if not present], "checks": checks}


def experiment_planning_agent(hypothesis: str, variables: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
    return {"hypothesis": hypothesis, "independent_variables": list(variables), "controls": constraints.get("controls", []), "safety_limits": constraints.get("safety_limits", {}), "sequence": ["baseline", "calibration", "sweep", "replication", "uncertainty", "archive_raw_data"]}


def hypothesis_generator(observations: list[str], domain_assumptions: list[str]) -> list[dict[str, Any]]:
    return [{"hypothesis": f"{observation} may be explained by {assumption}.", "test": f"Vary the parameter associated with {assumption} while controlling other conditions."} for observation in observations for assumption in domain_assumptions]


def research_roadmap(objective: str, evidence_gaps: list[str]) -> dict[str, Any]:
    phases = [{"phase": index + 1, "goal": gap, "exit_criterion": f"Independent evidence resolves: {gap}"} for index, gap in enumerate(evidence_gaps)]
    phases.append({"phase": len(phases) + 1, "goal": objective, "exit_criterion": "Design, simulation, fabrication, and measurement evidence agree within declared uncertainty."})
    return {"objective": objective, "phases": phases}


def update_model_from_experiments(model: dict[str, Any], experiments: list[dict[str, Any]], *, learning_rate: float = 0.2) -> dict[str, Any]:
    correction = dict(model.get("correction", {}))
    for experiment in experiments:
        for metric, measured in experiment.get("measured", {}).items():
            predicted = experiment.get("predicted", {}).get(metric)
            if predicted not in (None, 0):
                ratio = measured / predicted
                correction[metric] = (1.0 - learning_rate) * correction.get(metric, 1.0) + learning_rate * ratio
    return {**model, "correction": correction, "experiment_count": model.get("experiment_count", 0) + len(experiments)}


def autonomous_research_loop(idea: str, callbacks: dict[str, Callable[[Any], Any]]) -> dict[str, Any]:
    stages = ["literature", "circuit", "gds", "em", "quantum", "optimization", "fabrication", "measurement", "learning", "next_generation"]
    state: Any = {"idea": idea}
    history = []
    for stage in stages:
        callback = callbacks.get(stage)
        if callback is None:
            history.append({"stage": stage, "status": "external_adapter_required" if stage in {"fabrication", "measurement", "literature"} else "missing_callback"})
            continue
        state = callback(state)
        history.append({"stage": stage, "status": "completed"})
    return {"schema": "text-to-gds.autonomous-research-loop.v1", "history": history, "state": state}
