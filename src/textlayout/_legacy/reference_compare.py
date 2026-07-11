"""Literature-backed golden-device comparisons.

The functions in this module compare generated/extracted device metadata to
explicit JSON reference templates. They do not synthesize missing physics and
they do not treat skipped solvers as agreement evidence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from textlayout._legacy.synthesis import synthesize_resonator
from textlayout._paths import repository_root, resource_path

PROJECT_ROOT = repository_root()
REFERENCE_ROOT = resource_path("references")

REFERENCE_ALIASES = {
    "transmon": [
        REFERENCE_ROOT / "transmon" / "qiskit_metal_reference.json",
        REFERENCE_ROOT / "transmon" / "koch_2007.json",
    ],
    "jpa": [
        REFERENCE_ROOT / "jpa" / "castellanos_2007.json",
        REFERENCE_ROOT / "jpa" / "yamamoto_reference.json",
    ],
    "process": [REFERENCE_ROOT / "process" / "nb_trilayer_reference.json"],
    "jj_stack": [REFERENCE_ROOT / "process" / "nb_trilayer_reference.json"],
    "cpw": [REFERENCE_ROOT / "cpw" / "simons_reference.json"],
    "resonator": [REFERENCE_ROOT / "cpw" / "simons_reference.json"],
}


def quantum_stack_root(project_root: str | Path) -> Path:
    root = Path(project_root)
    nested = root / "quantum-eda-stack"
    if nested.exists():
        return nested
    sibling = root.parent / "quantum-eda-stack"
    return sibling


def compare_cpw_against_references(
    *,
    project_root: str | Path,
    output_dir: str | Path,
    frequency_ghz: float = 6.0,
) -> dict[str, Any]:
    """Compare our CPW synthesis metadata against available reference source files."""
    root = Path(project_root)
    stack = quantum_stack_root(root)
    refs = {
        "KQCircuits": stack / "KQCircuits" / "klayout_package" / "python" / "kqcircuits" / "elements" / "quarter_wave_cpw_resonator.py",
        "Qiskit Metal": stack / "qiskit-metal" / "src" / "qiskit_metal" / "analyses" / "em" / "cpw_calculations.py",
        "gdsfactory": stack / "gdsfactory" / "gdsfactory" / "components" / "quantum" / "resonator.py",
    }
    ours = synthesize_resonator(frequency_ghz=frequency_ghz, impedance_ohm=50.0)
    comparisons = []
    for name, path in refs.items():
        available = path.is_file()
        text = path.read_text(encoding="utf-8", errors="ignore")[:20_000] if available else ""
        comparisons.append(
            {
                "reference": name,
                "path": str(path),
                "available": available,
                "mentions_ports": "port" in text.lower(),
                "mentions_cpw": "cpw" in text.lower(),
                "mentions_layer": "layer" in text.lower(),
            }
        )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "text-to-gds.reference-comparison.v1",
        "stack_root": str(stack),
        "our_cpw": ours,
        "comparisons": comparisons,
        "verdict": "reference_files_found" if any(item["available"] for item in comparisons) else "references_missing",
    }
    report_path = out / "reference_cpw_comparison.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    image_path = out / "reference_cpw_comparison.png"
    _render_reference_comparison(report, image_path)
    report["report_path"] = str(report_path)
    report["image_path"] = str(image_path)
    return report


def _render_reference_comparison(report: dict[str, Any], output_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    refs = report["comparisons"]
    labels = [item["reference"] for item in refs]
    scores = [
        int(item["available"]) + int(item["mentions_ports"]) + int(item["mentions_cpw"]) + int(item["mentions_layer"])
        for item in refs
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(labels, scores, color=["#3866d6", "#30a66d", "#af52de"])
    ax.set_ylim(0, 4)
    ax.set_ylabel("Reference feature evidence")
    ax.set_title("CPW reference comparison")
    ax.grid(axis="y", alpha=0.25)
    ours = report["our_cpw"]
    ax.text(
        0.02,
        0.95,
        f"Our CPW: Z0={ours['impedance_ohm']:.2f} ohm, eps_eff={ours['epsilon_eff']:.3f}, L={ours['physical_length_um']:.1f} um",
        transform=ax.transAxes,
        va="top",
        family="monospace",
        fontsize=9,
    )
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def load_golden_reference(reference: str | Path | dict[str, Any] | list[Any]) -> dict[str, Any]:
    """Load a golden reference or merge a list of references."""
    if isinstance(reference, list):
        refs = [load_golden_reference(item) for item in reference]
        merged: dict[str, Any] = {
            "schema": "text-to-gds.golden-reference-merged.v1",
            "device_family": refs[0].get("device_family") if refs else "unknown",
            "reference_id": "+".join(str(ref.get("reference_id", "reference")) for ref in refs),
            "merged_references": refs,
            "topology": {"required_features": []},
            "parameters": {},
        }
        for ref in refs:
            merged["topology"]["required_features"].extend(
                ref.get("topology", {}).get("required_features", [])
                or ref.get("stack", {}).get("required_features", [])
            )
            merged["parameters"].update(ref.get("parameters", {}))
        return merged
    if isinstance(reference, dict):
        return reference
    raw = Path(reference)
    if not raw.is_absolute():
        alias = str(reference).lower()
        if alias in REFERENCE_ALIASES:
            return load_golden_reference(REFERENCE_ALIASES[alias])
        raw = PROJECT_ROOT / raw
    return json.loads(raw.read_text(encoding="utf-8"))


def default_references(device_family: str) -> dict[str, Any]:
    alias = device_family.lower()
    if alias not in REFERENCE_ALIASES:
        raise ValueError(f"no golden reference alias for {device_family!r}")
    return load_golden_reference(REFERENCE_ALIASES[alias])


def _device_payload(device: Any) -> dict[str, Any]:
    if isinstance(device, (str, Path)):
        return json.loads(Path(device).read_text(encoding="utf-8"))
    if isinstance(device, dict):
        return device

    payload: dict[str, Any] = {"class": device.__class__.__name__}
    if hasattr(device, "extract"):
        try:
            payload["extraction"] = device.extract()
        except Exception as exc:  # noqa: BLE001
            payload["extract_error"] = str(exc)
    if hasattr(device, "netlist"):
        try:
            netlist = device.netlist()
            payload["netlist"] = {
                "nets": [getattr(net, "name", str(net)) for net in getattr(netlist, "nets", [])],
                "parameters": getattr(netlist, "parameters", {}),
            }
        except Exception as exc:  # noqa: BLE001
            payload["netlist_error"] = str(exc)
    if hasattr(device, "ports"):
        try:
            payload["ports"] = list(device.ports().keys())
        except Exception as exc:  # noqa: BLE001
            payload["ports_error"] = str(exc)
    if hasattr(device, "geometry"):
        try:
            geometry = device.geometry()
            payload["info"] = dict(getattr(geometry, "info", {}) or {})
            payload["geometry_ports"] = list(getattr(geometry, "ports", {}).keys())
        except Exception as exc:  # noqa: BLE001
            payload["geometry_error"] = str(exc)
    return payload


def _deep_get(mapping: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        cur: Any = mapping
        ok = True
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok:
            return cur
    return None


def _generated_parameters(payload: dict[str, Any], family: str) -> dict[str, float]:
    info = payload.get("info", {}) if isinstance(payload.get("info"), dict) else {}
    extraction = payload.get("extraction", {}) if isinstance(payload.get("extraction"), dict) else {}
    net_params = _deep_get(payload, "netlist.parameters") or {}
    values: dict[str, float] = {}

    def put(name: str, value: Any, scale: float = 1.0) -> None:
        if value is None:
            return
        try:
            fval = float(value) * scale
        except (TypeError, ValueError):
            return
        if math.isfinite(fval):
            values[name] = fval

    for key in (
        "pad_width_um",
        "pad_height_um",
        "pad_gap_um",
        "connection_pad_width_um",
        "readout_resonator_length_um",
        "readout_resonator_width_um",
        "readout_resonator_gap_um",
        "coupling_gap_um",
        "cpw_trace_width_um",
        "cpw_gap_um",
    ):
        put(key, info.get(key))
    put("f0_ghz", info.get("center_frequency_ghz"))
    put("f0_ghz", info.get("target_frequency_ghz"))
    put("f01_ghz", info.get("center_frequency_ghz"))
    put("capacitance_ff", info.get("shunt_capacitance_ff"))
    put("impedance_ohm", _deep_get(info, "equivalent_circuit.Z0.value"))

    pocket = info.get("pocket_um")
    if isinstance(pocket, list) and len(pocket) >= 2:
        put("pocket_width_um", pocket[0])
        put("pocket_height_um", pocket[1])

    comparison = info.get("physics_target_comparison", {})
    if isinstance(comparison, dict):
        put("f01_ghz", comparison.get("scqubits_f01_ghz"))
        put("f01_ghz", comparison.get("target_f01_ghz"))
        put("alpha_mhz", comparison.get("scqubits_alpha_ghz"), 1000.0)
        put("alpha_mhz", comparison.get("target_alpha_ghz"), 1000.0)
        put("target_z0_ohm", comparison.get("layout_impedance_ohm"))

    for source in (net_params, info.get("synthesis", {}), extraction, info.get("extracted_parameters", {})):
        if not isinstance(source, dict):
            continue
        put("ej_over_ec", source.get("ej_over_ec"))
        put("ej_over_ec", source.get("EJ_over_EC"))
        put("capacitance_ff", source.get("capacitance_ff"))
        put("capacitance_ff", source.get("C_f"), 1e15)
        put("capacitance_ff", source.get("Cj"), 1e15)
        put("f01_ghz", source.get("frequency_ghz"))
        put("f01_ghz", source.get("f01_ghz"))
        put("alpha_mhz", source.get("alpha_ghz"), 1000.0)
        put("f0_ghz", source.get("f0"), 1e-9)
        put("f0_ghz", source.get("f0_hz"), 1e-9)
        put("impedance_ohm", source.get("impedance_ohm"))
        put("impedance_ohm", source.get("Z0"))
        put("target_z0_ohm", source.get("Z0"))
        put("physical_length_um", source.get("physical_length_um"))
        put("coupling_q", source.get("coupling_q"))
        put("lj_h", source.get("Lj"))
        put("lj_h", source.get("Lj_h"))
        put("l_h", source.get("L_h"))
        put("l_h", source.get("squid_array_inductance_h"))

    return values


def _required_feature_names(reference: dict[str, Any]) -> list[str]:
    features = (
        reference.get("topology", {}).get("required_features", [])
        or reference.get("stack", {}).get("required_features", [])
    )
    return [str(item.get("name", "")) for item in features if item.get("name")]


def _has_feature(payload: dict[str, Any], feature: str) -> bool:
    text = json.dumps(payload, sort_keys=True, default=str).lower()
    feature_l = feature.lower()
    synonyms = {
        "two superconducting islands": ["island_top", "island_bottom"],
        "split junction squid": ["squid", "junction"],
        "large shunt capacitance": ["pad_width", "pad_height"],
        "capacitive readout/control coupling": ["readout", "coupling"],
        "etched ground pocket": ["pocket"],
        "two charge island pads": ["pad_width", "pad_height"],
        "connection pad for readout coupling": ["connection_pad", "coupling"],
        "50 ohm feed": ["rf_feed", "50"],
        "coupling capacitor cc": ["coupling_capacitor", "coupling_capacitor_gap"],
        "lc resonator node": ["jpa_resonator_node"],
        "squid array carries resonator current": ["squid_connected_to_current_path", "squid_array"],
        "flux tuning": ["flux"],
        "pump path identified": ["pump"],
        "signal path identified": ["signal"],
        "galvanically isolated flux line": ["flux_bias"],
        "squid provides nonlinear resonator inductance": ["squid_array_inductance", "lj"],
        "m1 bottom electrode": ["m1", "bottom"],
        "alox tunnel barrier overlap": ["alox", "jj"],
        "m2 top electrode": ["m2", "top"],
        "via enclosure": ["via", "enclosure"],
        "junction isolation": ["isolation", "alox", "jj"],
        "center trace with two ground gaps": ["trace_width", "gap"],
        "lambda/4 resonator length": ["lambda", "physical_length"],
        "capacitive coupling to feedline": ["coupling", "feedline"],
        "airbridge placement across cpw grounds": ["airbridge"],
    }
    needles = synonyms.get(feature_l, [part for part in feature_l.replace("/", " ").split() if len(part) > 2])
    return all(needle in text for needle in needles)


def _compare_parameters(generated: dict[str, float], reference: dict[str, Any]) -> dict[str, Any]:
    errors: dict[str, Any] = {}
    for name, ref in reference.get("parameters", {}).items():
        if not isinstance(ref, dict):
            continue
        gen_name = {
            "target_z0_ohm": "target_z0_ohm",
            "feed_impedance_ohm": "impedance_ohm",
            "frequency_range_ghz": "f0_ghz",
            "canonical_ej_over_ec": "ej_over_ec",
        }.get(name, name)
        generated_value = generated.get(gen_name)
        if generated_value is None and name == "frequency_range_ghz":
            generated_value = generated.get("f01_ghz")
        if generated_value is None:
            errors[name] = {
                "status": "missing_generated_value",
                "reference": ref,
            }
            continue
        if "value" in ref and ref.get("unit") != "boolean":
            reference_value = float(ref["value"])
            diff_pct = (
                abs(generated_value - reference_value) / abs(reference_value) * 100.0
                if reference_value != 0.0
                else 0.0
            )
            errors[name] = {
                "status": "compared",
                "generated": generated_value,
                "reference": reference_value,
                "unit": ref.get("unit"),
                "difference_pct": diff_pct,
                "citation": ref.get("citation"),
            }
        elif "min" in ref and "max" in ref:
            lo = float(ref["min"])
            hi = float(ref["max"])
            if lo <= generated_value <= hi:
                distance = 0.0
            else:
                nearest = lo if generated_value < lo else hi
                distance = abs(generated_value - nearest) / max(abs(nearest), 1e-30) * 100.0
            errors[name] = {
                "status": "in_range" if distance == 0.0 else "out_of_range",
                "generated": generated_value,
                "reference_min": lo,
                "reference_max": hi,
                "unit": ref.get("unit"),
                "difference_pct": distance,
                "citation": ref.get("citation"),
            }
    return errors


def _numeric_error_values(parameter_error: dict[str, Any]) -> list[float]:
    values = []
    for row in parameter_error.values():
        if isinstance(row, dict) and isinstance(row.get("difference_pct"), (int, float)):
            values.append(float(row["difference_pct"]))
    return values


def _family_from_payload(payload: dict[str, Any], reference: dict[str, Any]) -> str:
    if reference.get("device_family"):
        return str(reference["device_family"]).lower()
    text = json.dumps(payload, default=str).lower()
    if "jpa" in text:
        return "jpa"
    if "transmon" in text:
        return "transmon"
    if "cpw" in text or "resonator" in text:
        return "cpw"
    if "process" in text or "alox" in text:
        return "process"
    return "unknown"


def golden_compare(device: Any, reference: str | Path | dict[str, Any] | list[Any] | None = None) -> dict[str, Any]:
    """Compare a generated device against cited golden references.

    Returns only comparisons that can be traced to generated/extracted metadata
    and cited reference values. Missing EM, capacitance, or solver quantities are
    reported as missing features/values rather than estimated.

    When topology and geometry features are available, also runs topology-aware
    reference matching for a richer feature-by-feature comparison.
    """
    payload = _device_payload(device)
    if reference is None:
        family_hint = _family_from_payload(payload, {})
        reference_obj = default_references(family_hint)
    else:
        reference_obj = load_golden_reference(reference)
    family = _family_from_payload(payload, reference_obj)
    generated = _generated_parameters(payload, family)

    features = _required_feature_names(reference_obj)
    missing_features = [feature for feature in features if not _has_feature(payload, feature)]
    topology_score = 1.0 if not features else max(0.0, (len(features) - len(missing_features)) / len(features))

    parameter_error = _compare_parameters(generated, reference_obj)
    fabrication_warnings: list[str] = []
    if family == "jpa" and not _has_feature(payload, "SQUID array carries resonator current"):
        fabrication_warnings.append("SQUID current path is not proven; JJ polygons may be decorative.")
    if family == "jpa" and not _has_feature(payload, "galvanically isolated flux line"):
        fabrication_warnings.append("Flux line galvanic isolation is not proven.")
    if family in {"cpw", "resonator"}:
        if "em_z0_ohm" not in generated:
            missing_features.append("EM Z0 comparison missing; no EM result supplied.")
        if "airbridge" not in json.dumps(payload, default=str).lower():
            fabrication_warnings.append("Airbridge placement is not present in extracted metadata.")
    if family in {"process", "jj_stack"}:
        for feature in ("M1 bottom electrode", "AlOx tunnel barrier overlap", "M2 top electrode", "via enclosure", "junction isolation"):
            if not _has_feature(payload, feature):
                fabrication_warnings.append(f"Process stack missing or unproven: {feature}.")

    numeric_errors = _numeric_error_values(parameter_error)
    comparison_rows = []
    for name, row in parameter_error.items():
        if not isinstance(row, dict) or row.get("generated") is None:
            continue
        reference_value = row.get("reference")
        if reference_value is None and row.get("reference_min") is not None and row.get("reference_max") is not None:
            reference_value = (float(row["reference_min"]) + float(row["reference_max"])) / 2.0
        if reference_value is not None:
            comparison_rows.append(
                {
                    "parameter": name,
                    "generated": row["generated"],
                    "reference": reference_value,
                    "unit": row.get("unit"),
                    "citation": row.get("citation"),
                    "status": row.get("status"),
                }
            )
    parameter_distance = sum(numeric_errors) / len(numeric_errors) if numeric_errors else 100.0
    missing_penalty = 100.0 * (1.0 - topology_score) + 5.0 * sum(
        1 for row in parameter_error.values() if row.get("status") == "missing_generated_value"
    )
    literature_distance = parameter_distance + missing_penalty

    result: dict[str, Any] = {
        "schema": "text-to-gds.golden-comparison.v1",
        "reference_id": reference_obj.get("reference_id"),
        "device_family": family,
        "topology_score": round(topology_score, 4),
        "parameter_error": parameter_error,
        "comparisons": comparison_rows,
        "missing_features": missing_features,
        "fabrication_warnings": fabrication_warnings,
        "literature_distance": round(literature_distance, 4),
        "generated_parameters": generated,
        "references": [
            {
                "reference_id": ref.get("reference_id"),
                "citation": ref.get("citation"),
            }
            for ref in reference_obj.get("merged_references", [reference_obj])
        ],
    }

    # Topology-aware reference matching (when topology data is available)
    topology_data = payload.get("topology") if isinstance(payload, dict) else None
    geometry_data = payload.get("geometry_features") if isinstance(payload, dict) else None
    if topology_data and isinstance(topology_data, dict):
        try:
            from textlayout._legacy.reference_matching import match_reference

            topology_result = topology_data if "detected_device" in topology_data else {
                "detected_device": topology_data.get("device", family),
                "confidence": topology_data.get("confidence", 0.5),
            }
            match = match_reference(
                topology_result,
                geometry_features=geometry_data,
                electrical_params=generated,
            )
            result["topology_aware_match"] = {
                "schema": match.get("schema"),
                "overall_score": match.get("overall_score"),
                "best_match": match.get("best_match"),
                "dimension_scores": match.get("dimension_scores"),
            }
        except Exception:
            pass

    return result


def write_golden_comparison(
    device: Any,
    reference: str | Path | dict[str, Any] | list[Any] | None,
    output_path: str | Path,
) -> dict[str, Any]:
    report = golden_compare(device, reference)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    return report
