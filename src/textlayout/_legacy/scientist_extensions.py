"""Topology discovery, digital twins, vision, literature, experiment, and tapeout intelligence."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Callable

import numpy as np

from textlayout._legacy.platform_extensions import friis_noise


def invent_circuit_topologies(requirements: dict[str, float]) -> list[dict[str, Any]]:
    """Generate distinct graph-level microwave/JPA architecture candidates."""
    target_bw = float(requirements.get("bandwidth_mhz", 100.0))
    candidates = [
        {"name": "single_pole_reflection_jpa", "nodes": ["port", "resonator", "ground"], "elements": ["coupling_C", "resonator_C", "SQUID_L"]},
        {"name": "two_pole_impedance_transformed_jpa", "nodes": ["port", "match", "resonator", "ground"], "elements": ["transformer", "coupling_C", "resonator_C", "SNAIL"]},
        {"name": "traveling_wave_distributed_amplifier", "nodes": ["input", "periodic_line", "output", "pump"], "elements": ["nonlinear_unit_cells", "phase_match_loads"]},
    ]
    for candidate in candidates:
        candidate["prior_score"] = 1.0 if (target_bw > 300 and "two_pole" in candidate["name"]) or (target_bw > 1000 and "traveling" in candidate["name"]) else 0.5
        candidate["requirements"] = requirements
    return sorted(candidates, key=lambda item: item["prior_score"], reverse=True)


def evolve_circuits(
    population: list[dict[str, Any]],
    fitness: Callable[[dict[str, Any]], float],
    mutate: Callable[[dict[str, Any], np.random.Generator], dict[str, Any]],
    *,
    generations: int = 20,
    population_size: int = 100,
    elite_fraction: float = 0.1,
    seed: int = 42,
) -> dict[str, Any]:
    if not population:
        raise ValueError("Initial circuit population is required")
    rng = np.random.default_rng(seed)
    current = [dict(item) for item in population]
    history = []
    for generation in range(generations):
        scored = sorted(((float(fitness(item)), item) for item in current), key=lambda pair: pair[0], reverse=True)
        elite_count = max(1, int(population_size * elite_fraction))
        elites = [dict(item) for _, item in scored[:elite_count]]
        history.append({"generation": generation, "best_fitness": scored[0][0], "mean_fitness": float(np.mean([score for score, _ in scored]))})
        current = elites[:]
        while len(current) < population_size:
            parent = elites[int(rng.integers(0, len(elites)))]
            current.append(mutate(dict(parent), rng))
    final = max(current, key=fitness)
    return {"best": final, "fitness": float(fitness(final)), "history": history}


def symbolic_microwave_reasoning(circuit: dict[str, Any]) -> dict[str, Any]:
    kinds = [element.get("kind") for element in circuit.get("elements", [])]
    expressions = []
    if "inductor" in kinds and "capacitor" in kinds:
        expressions.append({"quantity": "resonance", "expression": "f0 = 1/(2*pi*sqrt(L*C))"})
        expressions.append({"quantity": "lagrangian", "expression": "L = C*Phi_dot^2/2 - Phi^2/(2*L)"})
    if "josephson_junction" in kinds:
        expressions.extend([
            {"quantity": "josephson_energy", "expression": "U(phi) = -EJ*cos(phi)"},
            {"quantity": "hamiltonian", "expression": "H = 4*EC*(n-ng)^2 - EJ*cos(phi)"},
        ])
    if circuit.get("ports"):
        expressions.append({"quantity": "scattering", "expression": "S = (Z-Z0*I)*(Z+Z0*I)^-1"})
    return {"schema": "text-to-gds.symbolic-microwave-model.v1", "expressions": expressions, "assumptions": ["lossless unless R/G elements are present", "lumped approximation requires electrically short dimensions"]}


def discover_equation(
    variables: dict[str, list[float]], target: list[float], *, maximum_degree: int = 2
) -> dict[str, Any]:
    """Sparse symbolic regression over constant, powers, and pairwise products using BIC."""
    names = sorted(variables)
    arrays = {name: np.asarray(variables[name], dtype=float) for name in names}
    y = np.asarray(target, dtype=float)
    if any(array.shape != y.shape for array in arrays.values()):
        raise ValueError("Every variable must match target length")
    terms = [("1", np.ones_like(y))]
    for name in names:
        for degree in range(1, maximum_degree + 1):
            terms.append((name if degree == 1 else f"{name}^{degree}", arrays[name] ** degree))
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            terms.append((f"{left}*{right}", arrays[left] * arrays[right]))
    selected = [0]
    best_bic = math.inf
    while True:
        candidate_best = None
        for index in range(1, len(terms)):
            if index in selected:
                continue
            indices = selected + [index]
            design = np.column_stack([terms[item][1] for item in indices])
            coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
            residual = y - design @ coefficients
            rss = max(float(residual @ residual), 1e-30)
            bic = len(y) * math.log(rss / len(y)) + len(indices) * math.log(len(y))
            if candidate_best is None or bic < candidate_best[0]:
                candidate_best = (bic, index, coefficients, residual)
        if candidate_best is None or candidate_best[0] >= best_bic:
            break
        best_bic = candidate_best[0]
        selected.append(candidate_best[1])
    design = np.column_stack([terms[item][1] for item in selected])
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    expression = " + ".join(f"({coefficient:.8g})*{terms[index][0]}" for coefficient, index in zip(coefficients, selected, strict=True))
    prediction = design @ coefficients
    return {"expression": expression, "terms": [terms[index][0] for index in selected], "coefficients": coefficients.tolist(), "r_squared": float(1.0 - np.sum((y - prediction) ** 2) / max(np.sum((y - np.mean(y)) ** 2), 1e-30)), "bic": best_bic}


def select_approximation(*, electrical_length_rad: float, coupling_strength_fraction: float, geometry_3d: bool, required_relative_error: float) -> dict[str, Any]:
    if geometry_3d or required_relative_error < 0.005:
        model = "full_3d_em"
    elif electrical_length_rad > 0.3:
        model = "distributed_transmission_line_or_planar_em"
    elif coupling_strength_fraction > 0.1:
        model = "multimode_lumped_network"
    else:
        model = "lumped_lc"
    return {"selected_model": model, "inputs": {"electrical_length_rad": electrical_length_rad, "coupling_strength_fraction": coupling_strength_fraction, "geometry_3d": geometry_3d, "required_relative_error": required_relative_error}}


def full_cryostat_twin(stages: list[dict[str, Any]], components: list[dict[str, Any]]) -> dict[str, Any]:
    required = [300.0, 50.0, 4.0, 0.8, 0.1, 0.01]
    stage_temperatures = [float(stage["temperature_k"]) for stage in stages]
    missing = [temperature for temperature in required if not any(abs(value - temperature) <= max(0.02 * temperature, 0.005) for value in stage_temperatures)]
    noise_stages = []
    for component in components:
        loss_db = float(component.get("loss_db", 0.0))
        gain_db = float(component.get("gain_db", -loss_db))
        noise_stages.append({"name": component["name"], "gain_db": gain_db, "noise_temperature_k": float(component.get("noise_temperature_k", component.get("temperature_k", 0.0) * (10 ** (loss_db / 10) - 1)))})
    return {"schema": "text-to-gds.full-cryostat-twin.v1", "stages": stages, "components": components, "noise_budget": friis_noise(noise_stages), "missing_reference_stages_k": missing, "complete": not missing}


def magnetic_shielding_simulator(*, layers: list[dict[str, float]], external_field_t: float) -> dict[str, Any]:
    field = abs(external_field_t)
    rows = []
    for layer in layers:
        permeability = max(float(layer.get("relative_permeability", 1.0)), 1.0)
        thickness = float(layer["thickness_mm"])
        radius = float(layer["radius_mm"])
        factor = 1.0 + permeability * thickness / max(radius, 1e-30)
        if layer.get("superconducting", False) and abs(external_field_t) < layer.get("critical_field_t", math.inf):
            factor *= float(layer.get("meissner_factor", 1000.0))
        field /= factor
        rows.append({"name": layer.get("name", f"layer_{len(rows)}"), "shielding_factor": factor, "field_after_t": field})
    return {"external_field_t": external_field_t, "internal_field_t": math.copysign(field, external_field_t), "total_shielding_factor": abs(external_field_t) / max(field, 1e-30), "layers": rows}


def vibration_effect_model(*, displacement_psd_m2_per_hz: list[float], frequencies_hz: list[float], frequency_sensitivity_hz_per_m: float, gain_sensitivity_db_per_hz: float = 0.0) -> dict[str, Any]:
    psd, frequency = np.asarray(displacement_psd_m2_per_hz), np.asarray(frequencies_hz)
    displacement_rms = math.sqrt(float(np.trapz(psd, frequency)))
    jitter = abs(frequency_sensitivity_hz_per_m) * displacement_rms
    return {"displacement_rms_m": displacement_rms, "frequency_jitter_rms_hz": jitter, "gain_jitter_rms_db": jitter * abs(gain_sensitivity_db_per_hz)}


def predict_cooldown_failure(device: dict[str, float], cryostat: dict[str, float]) -> dict[str, Any]:
    risks = []
    differential_strain = abs(float(device.get("thermal_expansion_per_k", 0.0)) - float(device.get("substrate_expansion_per_k", 0.0))) * abs(float(cryostat.get("start_temperature_k", 300.0)) - float(cryostat.get("base_temperature_k", 0.01)))
    if differential_strain > float(device.get("maximum_strain", 1e-3)):
        risks.append("differential thermal contraction exceeds strain limit")
    if float(cryostat.get("residual_field_t", 0.0)) > float(device.get("maximum_field_t", math.inf)):
        risks.append("residual magnetic field exceeds device limit")
    if float(cryostat.get("input_noise_temperature_k", 0.0)) > float(device.get("maximum_input_noise_k", math.inf)):
        risks.append("input-chain noise exceeds device limit")
    return {"predicted_failure": bool(risks), "risks": risks, "differential_strain": differential_strain}


def understand_sem_image(image_path: str | Path, *, pixel_size_nm: float, threshold: int | None = None) -> dict[str, Any]:
    from PIL import Image

    gray = np.asarray(Image.open(image_path).convert("L"), dtype=float)
    used_threshold = float(np.median(gray)) if threshold is None else float(threshold)
    mask = gray >= used_threshold
    area_um2 = float(np.sum(mask)) * (pixel_size_nm / 1000.0) ** 2
    horizontal_edges = np.abs(np.diff(mask.astype(float), axis=1))
    vertical_edges = np.abs(np.diff(mask.astype(float), axis=0))
    perimeter_pixels = float(np.sum(horizontal_edges) + np.sum(vertical_edges))
    edge_positions = np.where(np.any(horizontal_edges > 0, axis=1))[0]
    roughness_nm = float(np.std(edge_positions) * pixel_size_nm) if edge_positions.size else 0.0
    isolated = mask & ~(
        np.roll(mask, 1, 0) | np.roll(mask, -1, 0) | np.roll(mask, 1, 1) | np.roll(mask, -1, 1)
    )
    defect_fraction = float(np.sum(isolated) / max(np.sum(mask), 1))
    return {"schema": "text-to-gds.sem-understanding.v1", "actual_area_um2": area_um2, "edge_perimeter_um": perimeter_pixels * pixel_size_nm / 1000.0, "edge_roughness_nm": roughness_nm, "defect_probability": min(1.0, defect_fraction * 10.0), "threshold": used_threshold}


def align_microscope_to_gds(reference: np.ndarray, microscope: np.ndarray, *, pixel_size_nm: float) -> dict[str, Any]:
    if reference.shape != microscope.shape:
        raise ValueError("Reference and microscope arrays must have equal registered dimensions")
    first = np.fft.fft2(reference - np.mean(reference))
    second = np.fft.fft2(microscope - np.mean(microscope))
    cross = first * second.conj()
    cross /= np.maximum(np.abs(cross), 1e-30)
    correlation = np.fft.ifft2(cross).real
    peak = np.unravel_index(np.argmax(correlation), correlation.shape)
    shift = np.asarray(peak, dtype=int)
    shift[shift > np.asarray(reference.shape) // 2] -= np.asarray(reference.shape)[shift > np.asarray(reference.shape) // 2]
    return {"shift_pixels_yx": shift.tolist(), "shift_nm_yx": (shift * pixel_size_nm).tolist(), "correlation_peak": float(correlation[peak])}


def train_yield_predictor(records: list[dict[str, Any]], feature_names: list[str], *, ridge: float = 1e-3) -> dict[str, Any]:
    x = np.asarray([[float(record["features"][name]) for name in feature_names] for record in records])
    y = np.asarray([float(record["yield_fraction"]) for record in records])
    mean, scale = np.mean(x, axis=0), np.maximum(np.std(x, axis=0), 1e-12)
    design = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    coefficients = np.linalg.solve(design.T @ design + ridge * np.eye(design.shape[1]), design.T @ y)
    prediction = np.clip(design @ coefficients, 0.0, 1.0)
    return {"feature_names": feature_names, "mean": mean.tolist(), "scale": scale.tolist(), "coefficients": coefficients.tolist(), "training_rmse": float(np.sqrt(np.mean((prediction - y) ** 2)))}


def predict_wafer_yield_ai(model: dict[str, Any], features: dict[str, float]) -> float:
    vector = np.asarray([features[name] for name in model["feature_names"]])
    design = np.r_[1.0, (vector - np.asarray(model["mean"])) / np.asarray(model["scale"])]
    return float(np.clip(design @ np.asarray(model["coefficients"]), 0.0, 1.0))


def fabrication_root_cause(problem: dict[str, float], process_changes: dict[str, float]) -> dict[str, Any]:
    causes = []
    ic_error = float(problem.get("ic_error_fraction", 0.0))
    pressure = float(process_changes.get("oxidation_pressure_fraction", 0.0))
    time = float(process_changes.get("oxidation_time_fraction", 0.0))
    angle = float(process_changes.get("evaporation_angle_deg", 0.0))
    area = float(process_changes.get("junction_area_fraction", 0.0))
    if ic_error < -0.05 and pressure > 0.0:
        causes.append({"cause": "oxidation pressure increase", "score": min(abs(ic_error) + pressure, 1.0)})
    if ic_error < -0.05 and time > 0.0:
        causes.append({"cause": "oxidation time increase", "score": min(abs(ic_error) + time, 1.0)})
    if abs(angle) > 0.5:
        causes.append({"cause": "evaporation angle offset", "score": min(abs(angle) / 3.0, 1.0)})
    if abs(area) > 0.03:
        causes.append({"cause": "lithographic junction-area error", "score": min(abs(area) * 5.0, 1.0)})
    return {"likely_causes": sorted(causes, key=lambda item: item["score"], reverse=True), "requires_metrology_confirmation": True}


def literature_watcher(known_ids: set[str], feed_entries: list[dict[str, Any]], *, keywords: list[str]) -> dict[str, Any]:
    matches = []
    for entry in feed_entries:
        text = f"{entry.get('title', '')} {entry.get('abstract', '')}".lower()
        if entry["id"] not in known_ids and any(keyword.lower() in text for keyword in keywords):
            matches.append(entry)
    return {"new_matches": matches, "new_ids": [entry["id"] for entry in matches], "watch_keywords": keywords}


def paper_to_executable_model(pdf_path: str | Path, *, fallback_text: str | None = None) -> dict[str, Any]:
    text = fallback_text
    backend = "provided_text"
    if text is None:
        try:
            from pypdf import PdfReader

            text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
            backend = "pypdf"
        except ImportError:
            return {"status": "prepared_missing_pdf_backend", "pdf_path": str(pdf_path), "install_hint": "uv add pypdf"}
    values = {"frequency_ghz": None, "gain_db": None, "bandwidth_mhz": None}
    patterns = {"frequency_ghz": r"(\d+(?:\.\d+)?)\s*GHz", "gain_db": r"(\d+(?:\.\d+)?)\s*dB\s*gain", "bandwidth_mhz": r"(\d+(?:\.\d+)?)\s*MHz"}
    for name, pattern in patterns.items():
        match = re.search(pattern, text or "", re.IGNORECASE)
        values[name] = float(match.group(1)) if match else None
    return {"status": "extracted_requires_review", "backend": backend, "pdf_path": str(pdf_path), "reported": values, "gds_plan": {"pcell": "lumped_element_jpa_seed", "parameters": values}, "simulation_plan": ["DRC", "EM", "JosephsonCircuits.jl", "comparison"], "automatic_claim_validation_required": True}


def verify_equation(*, observed: list[float], predicted: list[float], uncertainty: list[float] | None = None) -> dict[str, Any]:
    observed_values, predicted_values = np.asarray(observed), np.asarray(predicted)
    if observed_values.shape != predicted_values.shape:
        raise ValueError("Observed and predicted arrays must match")
    sigma = np.asarray(uncertainty) if uncertainty is not None else np.ones_like(observed_values)
    normalized = (observed_values - predicted_values) / np.maximum(sigma, 1e-30)
    return {"chi_squared": float(np.sum(normalized**2)), "reduced_chi_squared": float(np.mean(normalized**2)), "relative_rms_error": float(np.sqrt(np.mean((observed_values - predicted_values) ** 2)) / max(np.sqrt(np.mean(observed_values**2)), 1e-30)), "verified_within_2sigma": bool(np.all(np.abs(normalized) <= 2.0))}


def check_amplifier_claim(*, gain_db: float, bandwidth_hz: float, center_frequency_hz: float, added_noise_photons: float | None = None, pump_linewidth_hz: float | None = None) -> dict[str, Any]:
    gain_power = 10.0 ** (gain_db / 10.0)
    gbp = math.sqrt(gain_power) * bandwidth_hz
    checks = {"bandwidth_below_center": bandwidth_hz < center_frequency_hz, "finite_gain_bandwidth_product": math.isfinite(gbp), "quantum_noise_physical": added_noise_photons is None or added_noise_photons >= 0.5, "pump_linewidth_below_bandwidth": pump_linewidth_hz is None or pump_linewidth_hz < bandwidth_hz}
    return {"plausible": all(checks.values()), "checks": checks, "sqrt_gain_bandwidth_hz": gbp}


def autonomous_vna_tuning(
    measure: Callable[[float, float], float],
    *,
    center_hz: float,
    span_hz: float,
    initial_power_dbm: float,
    maximum_power_dbm: float,
    iterations: int = 5,
) -> dict[str, Any]:
    frequency, span, power = center_hz, span_hz, initial_power_dbm
    history = []
    for _ in range(iterations):
        frequencies = np.linspace(frequency - span / 2.0, frequency + span / 2.0, 41)
        values = [float(measure(float(point), power)) for point in frequencies]
        index = int(np.argmin(values))
        frequency = float(frequencies[index])
        history.append({"frequency_hz": frequency, "response": values[index], "span_hz": span, "power_dbm": power})
        span /= 4.0
        power = min(power + 1.0, maximum_power_dbm)
    return {"resonance_hz": frequency, "final_power_dbm": power, "history": history}


def bayesian_experiment_plan(observations: list[dict[str, Any]], candidates: list[dict[str, float]], parameter_names: list[str], *, exploration: float = 1.0) -> dict[str, Any]:
    if not candidates:
        raise ValueError("Experiment candidates are required")
    if not observations:
        return {"selected": candidates[0], "reason": "initial exploration"}
    x = np.asarray([[row["parameters"][name] for name in parameter_names] for row in observations])
    y = np.asarray([row["objective"] for row in observations])
    scale = np.maximum(np.std(x, axis=0), 1e-9)
    scores = []
    for candidate in candidates:
        point = np.asarray([candidate[name] for name in parameter_names])
        distance = np.sum(((x - point) / scale) ** 2, axis=1)
        weights = np.exp(-0.5 * distance)
        if np.sum(weights) <= 1e-15:
            mean, uncertainty = float(np.mean(y)), float(np.std(y) + 1.0)
        else:
            weights /= np.sum(weights)
            mean = float(weights @ y)
            uncertainty = math.sqrt(float(weights @ (y - mean) ** 2) + 1.0 / (1.0 + np.sum(np.exp(-0.5 * distance))))
        scores.append({"candidate": candidate, "mean": mean, "uncertainty": uncertainty, "acquisition": mean + exploration * uncertainty})
    selected = max(scores, key=lambda item: item["acquisition"])
    return {"selected": selected["candidate"], "prediction": selected, "candidates": scores}


def reinforcement_learning_jpa_tuning(transitions: list[dict[str, Any]], *, learning_rate: float = 0.2, discount: float = 0.95) -> dict[str, Any]:
    q: dict[tuple[str, str], float] = {}
    for transition in transitions:
        state = str(transition["state"])
        action = str(transition["action"])
        next_state = str(transition["next_state"])
        future = max((value for (candidate_state, _), value in q.items() if candidate_state == next_state), default=0.0)
        key = state, action
        q[key] = q.get(key, 0.0) + learning_rate * (float(transition["reward"]) + discount * future - q.get(key, 0.0))
    policy = {}
    for state, _ in q:
        choices = [(value, action) for (candidate_state, action), value in q.items() if candidate_state == state]
        policy[state] = max(choices)[1]
    return {"q_values": [{"state": state, "action": action, "value": value} for (state, action), value in q.items()], "policy": policy}


def diagnose_no_gain(evidence: dict[str, Any]) -> dict[str, Any]:
    checks = [
        ("pump_not_at_device", not evidence.get("pump_detected", False), "verify pump leakage/isolation and delivered power"),
        ("wrong_flux_bias", not evidence.get("resonance_flux_tuned", False), "sweep flux and locate the tunable resonance"),
        ("impedance_mismatch", float(evidence.get("return_loss_db", 100.0)) < 10.0, "inspect package and matching network"),
        ("pump_detuned", abs(float(evidence.get("pump_detuning_hz", 0.0))) > float(evidence.get("pump_tolerance_hz", math.inf)), "retune pump frequency"),
        ("device_saturated_or_damaged", evidence.get("critical_current_valid") is False, "measure Ic and reduce pump power"),
    ]
    findings = [{"cause": cause, "action": action} for cause, failed, action in checks if failed]
    return {"diagnosis": findings, "resolved": not findings}


def tapeout_checklist(evidence: dict[str, Any]) -> dict[str, Any]:
    checks = {"gds_frozen": bool(evidence.get("gds_hash")), "pdk_version_pinned": bool(re.fullmatch(r".+@\d+\.\d+\.\d+", str(evidence.get("process", "")))), "drc_passed": evidence.get("drc_passed") is True, "lvs_passed": evidence.get("lvs_passed") is True, "em_converged": evidence.get("em_converged") is True, "dfm_passed": evidence.get("dfm_passed") is True, "waiver_reviewed": evidence.get("waivers_reviewed") is True, "mask_visual_review": evidence.get("mask_reviewed") is True, "provenance_archived": evidence.get("provenance_archived") is True}
    return {"ready": all(checks.values()), "checks": checks, "blockers": [name for name, passed in checks.items() if not passed]}


def mask_review_ai(mask: dict[str, Any]) -> dict[str, Any]:
    findings = []
    if mask.get("empty_layers"):
        findings.append({"severity": "error", "finding": "required layers are empty", "layers": mask["empty_layers"]})
    if mask.get("orphan_labels", 0):
        findings.append({"severity": "warning", "finding": "orphan labels", "count": mask["orphan_labels"]})
    if mask.get("density_range", [0.0, 1.0])[1] > 0.9:
        findings.append({"severity": "warning", "finding": "local pattern density exceeds 90%"})
    if not mask.get("alignment_marks", False):
        findings.append({"severity": "error", "finding": "alignment marks missing"})
    return {"passed": not any(item["severity"] == "error" for item in findings), "findings": findings}


def electromagnetic_dfm(*, trace_width_um: float, corner_radius_um: float, via_pitch_um: float, wavelength_um: float, current_density_ratio: float) -> dict[str, Any]:
    checks = {"corner_radius": corner_radius_um >= trace_width_um, "via_pitch_electrically_small": via_pitch_um <= wavelength_um / 20.0, "current_density_margin": current_density_ratio <= 0.7}
    recommendations = []
    if not checks["corner_radius"]:
        recommendations.append("round corners to at least one trace width")
    if not checks["via_pitch_electrically_small"]:
        recommendations.append("reduce ground-via pitch below lambda/20")
    if not checks["current_density_margin"]:
        recommendations.append("widen conductor or parallel current paths")
    return {"passed": all(checks.values()), "checks": checks, "recommendations": recommendations}


def design_review_meeting_report(reviews: list[dict[str, Any]], decisions: list[dict[str, str]]) -> dict[str, Any]:
    blockers = [finding for review in reviews for finding in review.get("findings", []) if finding.get("severity") == "error"]
    actions = [decision for decision in decisions if decision.get("status", "open") != "closed"]
    return {"schema": "text-to-gds.design-review-report.v1", "review_count": len(reviews), "blockers": blockers, "decisions": decisions, "open_actions": actions, "approved": not blockers and not actions}


def quantum_device_leaderboard(devices: list[dict[str, Any]], weights: dict[str, float]) -> list[dict[str, Any]]:
    rows = []
    for device in devices:
        score = sum(weights[metric] * float(device.get(metric, 0.0)) for metric in weights)
        rows.append({**device, "score": score})
    rows.sort(key=lambda item: item["score"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def reproduction_score(metrics: dict[str, dict[str, float]], weights: dict[str, float] | None = None) -> dict[str, Any]:
    weights = weights or {name: 1.0 for name in metrics}
    rows = {}
    weighted = total = 0.0
    for name, values in metrics.items():
        reported, reproduced = float(values["reported"]), float(values["reproduced"])
        score = max(0.0, 1.0 - abs(reproduced - reported) / max(abs(reported), 1e-30))
        rows[name] = {**values, "score": score}
        weighted += weights.get(name, 1.0) * score
        total += weights.get(name, 1.0)
    return {"overall_score": weighted / max(total, 1e-30), "metrics": rows}


def multi_agent_research_lab(question: str, evidence: dict[str, Any]) -> dict[str, Any]:
    agents = [
        {"agent": "professor", "task": "define falsifiable research question", "output": question},
        {"agent": "designer", "task": "invent and parameterize device", "requires": ["requirements"]},
        {"agent": "simulation", "task": "run converged multi-solver EM", "requires": ["gds", "pdk"]},
        {"agent": "fabrication", "task": "check process migration, DFM, and yield", "requires": ["gds", "process"]},
        {"agent": "experimental", "task": "run calibrated safe measurement", "requires": ["device", "measurement_plan"]},
        {"agent": "reviewer", "task": "reject unsupported claims", "requires": ["simulation", "measurement", "uncertainty"]},
    ]
    available = set(evidence)
    for agent in agents:
        agent["ready"] = all(item in available for item in agent.get("requires", []))
    return {"schema": "text-to-gds.multi-agent-research-lab.v1", "question": question, "agents": agents}


def autonomous_quantum_scientist(goal: str, callbacks: dict[str, Callable[[Any], Any]]) -> dict[str, Any]:
    stages = ["literature", "topology_invention", "gds", "em", "quantum", "optimization", "mask", "fabrication", "measurement", "analysis", "publication"]
    state: Any = {"goal": goal}
    history = []
    for stage in stages:
        callback = callbacks.get(stage)
        if callback is None:
            status = "external_authority_required" if stage in {"fabrication", "measurement", "publication", "literature"} else "missing_callback"
        else:
            state = callback(state)
            status = "completed"
        history.append({"stage": stage, "status": status})
    return {"schema": "text-to-gds.autonomous-quantum-scientist.v1", "goal": goal, "history": history, "state": state, "claim_policy": "No claim is accepted without source, simulation/measurement evidence, uncertainty, and reviewer approval."}
