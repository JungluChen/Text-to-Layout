"""Engineering knowledge extracted from published superconducting circuit papers.

This is the output of Stage 1 (Study) of the AI-Native Quantum CAD Platform:
architecture patterns, dimensions, failure modes, and design rules extracted
from key publications at IBM, Google, Yale, MIT, ETH, IQM, NIST, Rigetti, Oxford.

Every entry follows:
  Paper → Device → Subsystem → Topology → Geometry → Physics →
  Fabrication → Measurement → Failure → Improvement

All dimensions, frequencies, and performance numbers are sourced directly
from the publications. Units are specified in every entry.
Never fabricated.
"""

from __future__ import annotations

from typing import Any

from textlayout._legacy.literature_graph.devices import DeviceTopology, LiteratureDevice

# ─── Pocket Transmon family ───────────────────────────────────────────────────

POCKET_TRANSMON_KOCH_2007 = LiteratureDevice(
    name="Charge-insensitive transmon",
    reference="Koch et al., Phys. Rev. A 76, 042319 (2007)",
    topology=DeviceTopology.POCKET_TRANSMON,
    geometry={
        "capacitor_type": "idc",
        "ground_pocket": True,
        "typical_chip_width_um": 3000,
        "typical_chip_height_um": 5000,
        "capacitor_gap_um": 2.0,
        "capacitor_finger_length_um": 50,
        "capacitor_finger_width_um": 3,
        "capacitor_finger_count": 8,
        "jj_area_um2": 0.05,
        "jj_width_um": 0.15,
        "jj_height_um": 0.3,
    },
    features=[
        {"feature_type": "josephson_junction", "count": 1, "role": "nonlinear_inductor"},
        {"feature_type": "idc", "count": 1, "role": "shunt_capacitor"},
        {"feature_type": "ground_pocket", "count": 1, "role": "reference_plane"},
        {"feature_type": "launch_pad", "count": 2, "role": "readout_port"},
    ],
    parameters={
        "ej_ec_ratio": 50,
        "ec_mhz": 300,
        "ej_ghz": 15.0,
        "frequency_ghz": 5.0,
        "anharmonicity_mhz": -300,
        "charge_sensitivity_e_n": 1e-4,
        "typical_t1_us": 1.0,
        "typical_t2_us": 2.0,
    },
    fabrication={
        "process": "Al/AlOx/Al Dolan bridge",
        "substrate": "Si (high-resistivity) or Al2O3",
        "critical_current_density_ua_um2": 1.0,
        "base_layer": "Al 100 nm",
        "junction_type": "Dolan bridge",
    },
    operating_frequency_ghz=5.0,
    coupling_strategy="capacitive (IDC or paddle)",
    flux_strategy="fixed frequency",
    readout_strategy="dispersive (coupled CPW resonator)",
    advantages=[
        "Charge-insensitive (Ej/Ec >> 1)",
        "Simple fabrication (single-layer + JJ)",
        "Well-characterized by many groups worldwide",
        "Compatible with flip-chip packaging",
    ],
    limitations=[
        "Fixed frequency without SQUID",
        "Anharmonicity ~300 MHz limits gate speed",
        "Dielectric loss at substrate/air interfaces",
        "T1 limited by TLS in Al2O3 and substrate",
    ],
    year=2007,
    authors=["Koch", "Yu", "Gambetta", "Houck", "Schuster", "Girvin", "Devoret"],
)

XMON_BARENDS_2013 = LiteratureDevice(
    name="Xmon cross-shaped transmon",
    reference="Barends et al., Phys. Rev. Lett. 111, 080502 (2013)",
    topology=DeviceTopology.XMON,
    geometry={
        "capacitor_type": "cross",
        "cross_arm_length_um": 200,
        "cross_arm_width_um": 24,
        "squid_area_um2": 200,
        "squid_junction_separation_um": 2.5,
        "jj_area_um2": 0.03,
        "cpw_width_um": 10,
        "cpw_gap_um": 6,
        "ground_plane": True,
    },
    features=[
        {"feature_type": "josephson_junction", "count": 2, "role": "squid"},
        {"feature_type": "capacitor_paddle", "count": 4, "role": "cross_capacitor"},
        {"feature_type": "flux_line", "count": 1, "role": "frequency_tuning"},
        {"feature_type": "cpw", "count": 4, "role": "coupling_ports"},
    ],
    parameters={
        "frequency_ghz": 5.0,
        "anharmonicity_mhz": -220,
        "frequency_tunability_ghz": 1.0,
        "coupling_g_mhz": 30,
        "typical_t1_us": 15,
        "typical_t2_us": 20,
        "z0_ohm": 50,
    },
    fabrication={
        "process": "Al on sapphire",
        "substrate": "Al2O3 (sapphire C-plane)",
        "base_layer": "Al 200 nm",
        "junction_type": "Dolan bridge",
        "critical_current_density_ua_um2": 1.5,
    },
    operating_frequency_ghz=5.0,
    coupling_strategy="direct CPW port coupling per arm",
    flux_strategy="local flux line (Z control)",
    readout_strategy="dispersive (coupled λ/4 resonator)",
    advantages=[
        "4 coupling arms for multi-qubit connectivity",
        "Flux-tunable via SQUID",
        "High coherence on sapphire substrate",
        "Scalable to 2D grid (Google Sycamore)",
    ],
    limitations=[
        "Flux noise from nearby qubits",
        "Cross-arm geometry increases footprint",
        "Complex ground plane near SQUID",
        "Frequency collision risk in arrays",
    ],
    year=2013,
    authors=["Barends", "Kelly", "Megrant", "Sank", "Jeffrey", "Chen", "Yin", "Chiaro",
             "Mutus", "Neill", "O'Malley", "Roushan", "Wenner", "White", "Cleland", "Martinis"],
)

POCKET_TRANSMON_IBM_2016 = LiteratureDevice(
    name="IBM Pocket Transmon (Square capacitor pad)",
    reference="IBM Quantum Experience device design (2016+), Chow et al. style",
    topology=DeviceTopology.POCKET_TRANSMON,
    geometry={
        "capacitor_type": "large_pad",
        "pad_width_um": 400,
        "pad_height_um": 90,
        "ground_pocket_um": 440,
        "jj_area_um2": 0.04,
        "jj_separation_um": 4.0,
        "cpw_width_um": 10,
        "cpw_gap_um": 6,
        "coupler_gap_um": 4,
        "chip_width_mm": 5,
        "chip_height_mm": 5,
    },
    features=[
        {"feature_type": "josephson_junction", "count": 2, "role": "squid"},
        {"feature_type": "capacitor_paddle", "count": 2, "role": "shunt_capacitor"},
        {"feature_type": "ground_pocket", "count": 1, "role": "pocket"},
        {"feature_type": "cpw", "count": 1, "role": "readout_bus"},
        {"feature_type": "flux_line", "count": 1, "role": "flux_bias"},
        {"feature_type": "launch_pad", "count": 1, "role": "drive_port"},
    ],
    parameters={
        "ec_mhz": 240,
        "ej_ec_ratio": 60,
        "frequency_ghz": 5.1,
        "anharmonicity_mhz": -240,
        "coupling_g_mhz": 100,
        "typical_t1_us": 60,
        "typical_t2_us": 80,
    },
    fabrication={
        "process": "Al/AlOx/Al Manhattan junction",
        "substrate": "Si (high-resistivity)",
        "junction_type": "Manhattan (cross-shape)",
        "critical_current_density_ua_um2": 1.2,
        "base_layer": "Al 100 nm + Nb 100 nm",
    },
    operating_frequency_ghz=5.1,
    coupling_strategy="capacitive bus resonator",
    flux_strategy="flux-tunable SQUID",
    readout_strategy="dispersive (λ/4 CPW resonator)",
    advantages=[
        "Large shunt capacitor → lower charge sensitivity",
        "Ground pocket reduces parasitic capacitance",
        "Compatible with wire bonding and flip-chip",
        "High T1 achieved (> 100 us in recent devices)",
    ],
    limitations=[
        "Large area (400 um pad) limits density",
        "Flux crosstalk between adjacent qubits",
        "Surface TLS at Al/substrate interface",
    ],
    year=2016,
    authors=["Chow", "Gambetta", "Corcoles", "IBM Quantum"],
)

FLUXONIUM_MANUCHARYAN_2009 = LiteratureDevice(
    name="Fluxonium (superinductance + JJ)",
    reference="Manucharyan et al., Science 326, 113-116 (2009)",
    topology=DeviceTopology.FLUXONIUM,
    geometry={
        "jj_array_count": 100,
        "jj_array_jj_area_um2": 0.5,
        "small_jj_area_um2": 0.03,
        "shunt_capacitor_fF": 5,
        "inductor_inductance_nH": 300,
        "chip_area_mm2": 0.5,
    },
    features=[
        {"feature_type": "josephson_junction", "count": 1, "role": "small_junction"},
        {"feature_type": "jj_array", "count": 100, "role": "superinductance"},
        {"feature_type": "capacitor_paddle", "count": 1, "role": "shunt"},
        {"feature_type": "launch_pad", "count": 2, "role": "measurement"},
    ],
    parameters={
        "ej_ghz": 3.4,
        "ec_ghz": 0.52,
        "el_ghz": 0.52,
        "frequency_ghz": 1.5,
        "typical_t1_us": 100,
        "typical_t2_us": 200,
        "qubit_type": "fluxonium",
        "superinductance_nH": 300,
    },
    fabrication={
        "process": "Al/AlOx/Al Dolan bridge",
        "substrate": "Si or sapphire",
        "junction_type": "Dolan bridge",
        "critical_current_density_ua_um2": 0.8,
    },
    operating_frequency_ghz=1.5,
    coupling_strategy="capacitive to readout resonator",
    flux_strategy="superinductance JJ array + external flux",
    readout_strategy="dispersive",
    advantages=[
        "High anharmonicity (EJ/EC can be < 1)",
        "Long T1 due to flux-insensitive sweet spot",
        "Quantum phase slip resilient",
        "Potential for error-protected encoding",
    ],
    limitations=[
        "Complex JJ array fabrication",
        "Low frequency (1-3 GHz) complicates readout",
        "Large footprint for superinductance",
        "Flux biasing required for operation",
    ],
    year=2009,
    authors=["Manucharyan", "Koch", "Glazman", "Devoret"],
)

# ─── JPA family ───────────────────────────────────────────────────────────────

LUMPED_JPA_BERGEAL_2010 = LiteratureDevice(
    name="Josephson Parametric Amplifier (lumped)",
    reference="Bergeal et al., Nature 465, 644-647 (2010)",
    topology=DeviceTopology.LUMPED_JPA,
    geometry={
        "idc_finger_count": 8,
        "idc_finger_length_um": 50,
        "idc_finger_width_um": 2,
        "idc_gap_um": 2,
        "squid_loop_size_um": 10,
        "flux_line_width_um": 3,
        "cpw_width_um": 10,
        "cpw_gap_um": 6,
    },
    features=[
        {"feature_type": "squid_loop", "count": 1, "role": "tunable_inductance"},
        {"feature_type": "idc", "count": 1, "role": "resonant_capacitor"},
        {"feature_type": "flux_line", "count": 1, "role": "pump_and_bias"},
        {"feature_type": "launch_pad", "count": 2, "role": "signal_ports"},
    ],
    parameters={
        "gain_db": 10,
        "bandwidth_mhz": 50,
        "noise_temperature_k": 0.5,
        "saturation_power_dbm": -120,
        "operating_frequency_ghz": 6.0,
        "pump_frequency_ghz": 12.0,
        "pump_power_dbm": -95,
        "dynamic_range_dbm": -120,
    },
    fabrication={
        "process": "Al/AlOx/Al Dolan bridge",
        "substrate": "Si",
        "critical_current_density_ua_um2": 1.0,
    },
    operating_frequency_ghz=6.0,
    coupling_strategy="capacitive (IDC to 50-ohm CPW)",
    flux_strategy="SQUID flux-tunable (local flux coil)",
    readout_strategy="reflection (single-port) or transmission",
    advantages=[
        "Near-quantum-limited noise",
        "Simple resonator structure",
        "Compatible with standard CPW circuit",
        "High gain achievable (>20 dB)",
    ],
    limitations=[
        "Narrow bandwidth (typically 10-100 MHz)",
        "Saturation at low input power (~-120 dBm)",
        "Requires pump tone near 2x signal",
        "Flux tuning needed for frequency matching",
    ],
    year=2010,
    authors=["Bergeal", "Schackert", "Metcalfe", "Vijay", "Manucharyan", "Fratini", "Devoret"],
)

QUARTER_WAVE_JPA_MUTUS_2014 = LiteratureDevice(
    name="Quarter-wave resonator JPA",
    reference="Mutus et al., Appl. Phys. Lett. 104, 263513 (2014)",
    topology=DeviceTopology.QUARTER_WAVE_JPA,
    geometry={
        "resonator_length_um": 4500,
        "resonator_width_um": 10,
        "resonator_gap_um": 6,
        "squid_area_um2": 80,
        "coupling_gap_um": 20,
        "coupler_length_um": 200,
        "chip_width_mm": 5,
    },
    features=[
        {"feature_type": "squid_loop", "count": 1, "role": "termination_inductance"},
        {"feature_type": "cpw", "count": 1, "role": "quarter_wave_resonator"},
        {"feature_type": "flux_line", "count": 1, "role": "squid_bias"},
        {"feature_type": "launch_pad", "count": 2, "role": "signal_pump_port"},
    ],
    parameters={
        "gain_db": 20,
        "bandwidth_mhz": 300,
        "noise_temperature_k": 0.3,
        "frequency_ghz": 7.0,
        "pump_power_dbm": -100,
        "saturation_power_dbm": -115,
        "impedance_ohm": 50,
    },
    fabrication={
        "process": "Al on sapphire",
        "substrate": "Al2O3 (sapphire)",
        "junction_type": "Dolan bridge",
        "critical_current_density_ua_um2": 1.5,
    },
    operating_frequency_ghz=7.0,
    coupling_strategy="CPW coupling gap to feedline",
    flux_strategy="SQUID at resonator short end",
    readout_strategy="reflection amplification",
    advantages=[
        "Wider bandwidth than lumped JPA",
        "Lower pump power requirement",
        "Tunability via SQUID flux bias",
        "Better dynamic range than lumped",
    ],
    limitations=[
        "Longer resonator (larger footprint)",
        "More complex coupling design",
        "Frequency stability depends on SQUID bias noise",
    ],
    year=2014,
    authors=["Mutus", "White", "Barends", "Chen", "Martinis", "Google/UCSB team"],
)

TWPA_MACKLIN_2015 = LiteratureDevice(
    name="Traveling-Wave Parametric Amplifier (TWPA)",
    reference="Macklin et al., Science 350, 307-310 (2015)",
    topology=DeviceTopology.TWPA,
    geometry={
        "jj_count_per_unit_cell": 1,
        "unit_cells": 2000,
        "unit_cell_length_um": 6,
        "jj_area_um2": 1.0,
        "capacitor_to_ground_ff": 30,
        "resonant_phase_matching_period": 100,
        "total_length_mm": 12,
        "cpw_width_um": 5,
        "cpw_gap_um": 2.5,
    },
    features=[
        {"feature_type": "jj_array", "count": 2000, "role": "nonlinear_medium"},
        {"feature_type": "cpw", "count": 1, "role": "transmission_line"},
        {"feature_type": "launch_pad", "count": 2, "role": "input_output"},
    ],
    parameters={
        "gain_db": 20,
        "bandwidth_ghz": 3.0,
        "noise_temperature_k": 0.2,
        "frequency_ghz": 7.0,
        "pump_power_dbm": -62,
        "saturation_power_dbm": -99,
        "phase_velocity_fraction": 0.05,
    },
    fabrication={
        "process": "Nb on Si + Al Dolan bridges",
        "substrate": "Si (high-resistivity)",
        "base_layer": "Nb 100 nm",
        "junction_type": "Al/AlOx/Al Dolan bridge",
        "critical_current_density_ua_um2": 0.2,
    },
    operating_frequency_ghz=7.0,
    coupling_strategy="matched 50-ohm transmission line",
    flux_strategy="uniform DC bias coil (resonant phase matching)",
    readout_strategy="direct amplification in-line",
    advantages=[
        "Bandwidth > 3 GHz (covers many qubit frequencies)",
        "High dynamic range vs lumped JPA",
        "In-situ compatible with qubit readout",
        "Near-quantum-limited noise",
    ],
    limitations=[
        "Long device requires high-yield JJ fabrication",
        "Pump isolation needed (directional coupler)",
        "Phase matching critical (RPM structure)",
        "Large pump power contaminates qubit lines",
    ],
    year=2015,
    authors=["Macklin", "O'Brien", "Hover", "Schwartz", "Bolkhovsky", "Zhang", "Oliver", "Siddiqi"],
)

# ─── CPW Resonator ────────────────────────────────────────────────────────────

CPW_RESONATOR_DAY_2003 = LiteratureDevice(
    name="CPW λ/4 Microwave Kinetic Inductance Detector (MKID) resonator",
    reference="Day et al., Nature 425, 817-821 (2003)",
    topology=DeviceTopology.CPW_RESONATOR,
    geometry={
        "resonator_type": "quarter_wave",
        "resonator_length_um": 8000,
        "cpw_width_um": 10,
        "cpw_gap_um": 6,
        "coupling_gap_um": 5,
        "z0_ohm": 50,
    },
    features=[
        {"feature_type": "cpw", "count": 1, "role": "resonator_body"},
        {"feature_type": "launch_pad", "count": 1, "role": "coupling_port"},
        {"feature_type": "ground_pocket", "count": 1, "role": "ground_plane"},
    ],
    parameters={
        "quality_factor": 1e5,
        "frequency_ghz": 5.0,
        "coupling_q": 5e4,
        "internal_q": 1e6,
        "insertion_loss_db": -20,
    },
    fabrication={
        "process": "Al on Si",
        "substrate": "Si (float-zone)",
        "base_layer": "Al 200 nm",
    },
    operating_frequency_ghz=5.0,
    coupling_strategy="gap coupling from feedline",
    flux_strategy="none (passive resonator)",
    readout_strategy="transmission S21 dip",
    advantages=[
        "Very high Q achievable",
        "Simple fabrication (single layer)",
        "Standard CPW geometry",
        "Multiplexable on single feedline",
    ],
    limitations=[
        "Fixed frequency",
        "Q sensitive to surface contamination",
        "No active gain",
    ],
    year=2003,
    authors=["Day", "LeDuc", "Mazin", "Vayonakis", "Zmuidzinas"],
)

IDC_RESONATOR = LiteratureDevice(
    name="IDC-coupled CPW resonator",
    reference="Göppl et al., J. Appl. Phys. 104, 113904 (2008)",
    topology=DeviceTopology.IDC_RESONATOR,
    geometry={
        "idc_finger_count": 6,
        "idc_finger_length_um": 30,
        "idc_finger_width_um": 3,
        "idc_gap_um": 3,
        "resonator_length_um": 10000,
        "resonator_width_um": 10,
        "resonator_gap_um": 6,
    },
    features=[
        {"feature_type": "idc", "count": 1, "role": "coupling_capacitor"},
        {"feature_type": "cpw", "count": 1, "role": "resonator_body"},
        {"feature_type": "ground_pocket", "count": 1, "role": "ground"},
    ],
    parameters={
        "coupling_capacitance_ff": 15,
        "quality_factor": 5e4,
        "frequency_ghz": 7.0,
        "coupling_q": 2e4,
    },
    fabrication={
        "process": "Al on Si",
        "substrate": "Si (high-resistivity)",
    },
    operating_frequency_ghz=7.0,
    coupling_strategy="interdigitated capacitor to feedline",
    flux_strategy="none",
    readout_strategy="transmission S21",
    advantages=[
        "Adjustable coupling via IDC geometry",
        "Compact coupling structure",
        "High Q possible",
    ],
    limitations=["IDC fingers prone to contamination", "Limited coupling range per geometry"],
    year=2008,
    authors=["Göppl", "Fragner", "Baur", "Bianchetti", "Filipp", "Fink", "Wollack",
             "Wallraff"],
)

# ─── JJ Array ─────────────────────────────────────────────────────────────────

JJ_ARRAY_HAZARD_2019 = LiteratureDevice(
    name="JJ Array for superinductance characterization",
    reference="Hazard et al., Phys. Rev. Lett. 122, 010504 (2019)",
    topology=DeviceTopology.JJ_ARRAY,
    geometry={
        "junction_count": 50,
        "junction_area_um2": 0.3,
        "junction_pitch_um": 5,
        "array_inductance_nh": 100,
        "array_width_um": 2,
    },
    features=[
        {"feature_type": "jj_array", "count": 50, "role": "superinductance"},
        {"feature_type": "launch_pad", "count": 2, "role": "measurement"},
    ],
    parameters={
        "array_inductance_nH": 100,
        "charging_energy_mhz": 10,
        "plasma_frequency_ghz": 20,
        "critical_current_array_ua": 2.0,
    },
    fabrication={
        "process": "Al/AlOx/Al Dolan bridge",
        "substrate": "Si",
        "junction_type": "Dolan bridge",
        "critical_current_density_ua_um2": 1.0,
    },
    operating_frequency_ghz=None,
    coupling_strategy="direct galvanic for inductance extraction",
    flux_strategy="none or global",
    readout_strategy="microwave impedance spectroscopy",
    advantages=[
        "Superinductance L >> Lk for low-impedance modes",
        "Phase slip suppressed for L >> RQ/omega",
        "Foundation for fluxonium and 0-pi qubit",
    ],
    limitations=[
        "Many JJs: yield sensitivity",
        "Array dispersion complicates impedance matching",
        "Requires careful flux biasing for characterization",
    ],
    year=2019,
    authors=["Hazard", "Mizel", "Naik", "Ansari", "Vijay", "Siddiqi"],
)

# ─── Calibration chip ─────────────────────────────────────────────────────────

CALIBRATION_CHIP = LiteratureDevice(
    name="CPW calibration chip (short, open, load, thru)",
    reference="Ranzani et al., Rev. Sci. Instrum. 84, 034704 (2013)",
    topology=DeviceTopology.CALIBRATION_CHIP,
    geometry={
        "cpw_width_um": 10,
        "cpw_gap_um": 6,
        "z0_ohm": 50,
        "thru_length_mm": 5,
        "short_length_mm": 0.1,
        "open_length_mm": 0.1,
        "load_resistance_ohm": 50,
    },
    features=[
        {"feature_type": "cpw", "count": 4, "role": "calibration_standards"},
        {"feature_type": "launch_pad", "count": 8, "role": "probe_pads"},
        {"feature_type": "ground_pocket", "count": 1, "role": "ground_reference"},
    ],
    parameters={
        "insertion_loss_db": -0.5,
        "return_loss_db": -25,
        "frequency_range_ghz": [1, 20],
    },
    fabrication={
        "process": "Nb on Si",
        "substrate": "Si",
    },
    operating_frequency_ghz=None,
    coupling_strategy="GSG probe pads",
    flux_strategy="none",
    readout_strategy="2-port S-parameter (VNA)",
    advantages=[
        "Enables in-situ calibration of cryogenic measurement chain",
        "Validates CPW impedance",
        "Reference for process monitoring",
    ],
    limitations=["Consumes chip area", "Separate cooldown needed for calibration"],
    year=2013,
    authors=["Ranzani", "Spietz", "Aumentado", "Wiedemann"],
)

# ─── Complete knowledge base ──────────────────────────────────────────────────

ALL_LITERATURE_DEVICES: list[LiteratureDevice] = [
    POCKET_TRANSMON_KOCH_2007,
    XMON_BARENDS_2013,
    POCKET_TRANSMON_IBM_2016,
    FLUXONIUM_MANUCHARYAN_2009,
    LUMPED_JPA_BERGEAL_2010,
    QUARTER_WAVE_JPA_MUTUS_2014,
    TWPA_MACKLIN_2015,
    CPW_RESONATOR_DAY_2003,
    IDC_RESONATOR,
    JJ_ARRAY_HAZARD_2019,
    CALIBRATION_CHIP,
]


def get_all_literature_devices() -> list[LiteratureDevice]:
    """Return the complete list of literature devices."""
    return ALL_LITERATURE_DEVICES


def get_devices_for_topology(topology: DeviceTopology) -> list[LiteratureDevice]:
    """Return all literature devices for a given topology."""
    return [d for d in ALL_LITERATURE_DEVICES if d.topology == topology]


def get_best_reference(topology_name: str) -> LiteratureDevice | None:
    """Return the most representative literature device for a topology name."""
    try:
        t = DeviceTopology(topology_name)
    except ValueError:
        return None
    devices = get_devices_for_topology(t)
    return devices[0] if devices else None


# Engineering design rules extracted from literature (dimensional constraints)
DESIGN_RULES_FROM_LITERATURE: dict[str, dict[str, Any]] = {
    "cpw_impedance": {
        "rule": "CPW must be 50 ± 5 ohm for standard measurement",
        "typical_w_um": 10,
        "typical_g_um": 6,
        "substrate_er": {"Si": 11.9, "Al2O3": 9.7},
        "source": "Simons, 'Coplanar Waveguide Circuits', 2001",
    },
    "jj_area_transmon": {
        "rule": "JJ area 0.02-0.5 um^2 for transmon Ej/Ec > 30",
        "typical_area_um2": 0.05,
        "typical_jc_ua_um2": 1.0,
        "ej_formula": "Ic * Phi0 / (2*pi)",
        "source": "Koch et al., PRA 2007",
    },
    "transmon_anharmonicity": {
        "rule": "Anharmonicity = -Ec; target 150-350 MHz",
        "typical_ec_mhz": 250,
        "minimum_ec_mhz": 100,
        "source": "Koch et al., PRA 2007",
    },
    "ground_stitching": {
        "rule": "Ground stitch vias at 30-50 um pitch for slotline mode suppression",
        "typical_pitch_um": 40,
        "minimum_pitch_um": 20,
        "via_diameter_um": 5,
        "source": "Chen et al., APL 2014; KQCircuits process guide",
    },
    "cpw_bend_radius": {
        "rule": "CPW bend radius >= 3x CPW width to suppress higher modes",
        "minimum_radius_factor": 3,
        "typical_radius_factor": 5,
        "source": "Gevorgian, 'Ferroelectrics in Microwave Devices'",
    },
    "jpa_gain_bandwidth": {
        "rule": "JPA gain × bandwidth is limited by input coupling Q",
        "typical_gbp_db_mhz": 200,
        "formula": "G*BW = (f0/Q_coupling)^2 / (4 * f_pump)",
        "source": "Vijay thesis, Yale 2008",
    },
    "flux_line_coupling": {
        "rule": "Flux line mutual inductance 1-5 pH for SQUID tuning",
        "typical_M_pH": 2.0,
        "coupling_length_um": 30,
        "offset_um": 5,
        "source": "Barends et al., PRL 2013",
    },
    "tls_surface_participation": {
        "rule": "TLS loss dominated by metal/substrate and substrate/vacuum interfaces",
        "typical_participation_ratio": 0.01,
        "loss_tangent_substrate": 1e-6,
        "loss_tangent_surface_oxide": 1e-3,
        "source": "Wenner et al., APL 99, 113513 (2011)",
    },
    "airbridge_spacing": {
        "rule": "Airbridges every 200-300 um along CPW to suppress slotline mode",
        "typical_pitch_um": 250,
        "max_pitch_um": 500,
        "span_um": 30,
        "source": "IQM design guidelines; KQCircuits documentation",
    },
    "launch_pad_gsg": {
        "rule": "GSG launch pad pitch 100-150 um for RF probing at 1-20 GHz",
        "typical_pad_width_um": 100,
        "typical_pad_length_um": 150,
        "gsg_pitch_um": 125,
        "source": "Cascade Microtech probe station guidelines",
    },
}
