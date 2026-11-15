"""Read-only scalar/vector JTWPA diagnostic for an isolated Python/NumPy runtime."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np


source = Path("/src/src/textlayout/_legacy/jtwpa.py")
spec = importlib.util.spec_from_file_location("jtwpa_probe_module", source)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

config = module.gaydamachenko_reference_config()
frequencies = np.array([1.0, 6.7, 12.92, 25.84, 39.0])
omega_cubed = (2.0 * math.pi * frequencies * 1e9) ** 3
matrices = module._unit_cell_abcd(frequencies, config)
bands = module.jtwpa_stop_bands(config)
scalar_vector_differences = []
for index, frequency in enumerate(frequencies):
    omega = 2.0 * math.pi * float(frequency) * 1e9
    inductance = config.squid_inductance_ph * 1e-12
    junction_capacitance = config.junction_capacitance_ff * 1e-15
    denominator = 1.0 - omega**2 * junction_capacitance * inductance
    a, b, c, d = 1 + 0j, 0j, 0j, 1 + 0j
    for capacitance_ff in config.capacitance_profile_ff:
        capacitance = capacitance_ff * 1e-15
        cell_a = 1.0 - 0.5 * omega**2 * inductance * capacitance / denominator
        cell_b = 1j * omega * inductance / denominator
        cell_c = 1j * omega * capacitance - (
            0.25j * omega**3 * inductance * capacitance**2 / denominator
        )
        a, b, c, d = (
            a * cell_a + b * cell_c,
            a * cell_b + b * cell_a,
            c * cell_a + d * cell_c,
            c * cell_b + d * cell_a,
        )
    differences = [abs(scalar - vector[index]) for scalar, vector in zip((a, b, c, d), matrices)]
    scalar_vector_differences.append(float(max(differences)))

report = {
    "schema": "textlayout.jtwpa-runtime-diagnostic.v1",
    "python": sys.version,
    "platform": platform.platform(),
    "architecture": platform.machine(),
    "numpy": np.__version__,
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "frequency_ghz": frequencies.tolist(),
    "omega_cubed": [float(value) for value in omega_cubed],
    "matrix_entries_finite": [
        [bool(np.isfinite(value)) for value in matrix] for matrix in matrices
    ],
    "scalar_vector_max_absolute_difference": scalar_vector_differences,
    "band_count": len(bands),
    "bands": bands,
}
print(json.dumps(report, indent=2, allow_nan=False))
