import math
import json
from pathlib import Path
import pytest
from textlayout.solvers import scqubits_adapter as adapter
from textlayout._legacy.extraction_schema import ej_ghz

@pytest.mark.parametrize('energy_ghz', [15.0, 30.0])
def test_legacy_josephson_exact_si_identity(energy_ghz):
    current = 4 * math.pi * 1.602176634e-19 * energy_ghz * 1e9
    assert ej_ghz(current) == pytest.approx(energy_ghz, rel=1e-14)

@pytest.mark.parametrize('energy_ghz', [15.0, 30.0])
def test_product_josephson_exact_si_identity(tmp_path, energy_ghz):
    pytest.importorskip('scqubits')
    current = 4 * math.pi * 1.602176634e-19 * energy_ghz * 1e9
    result = adapter.execute_scqubits(adapter.prepare_scqubits_input(
        {'ic_a':current, 'capacitance_f':80e-15}, tmp_path))
    assert result.status == 'executed', result.reason
    payload = json.loads(Path(result.artifacts['result']).read_text())
    assert payload['solver_inputs']['EJ_GHz'] == pytest.approx(energy_ghz, rel=1e-14)
    assert payload['convergence'] == 'NOT_EVALUATED'
    assert payload['reference_comparison'] == 'NOT_EVALUATED'
