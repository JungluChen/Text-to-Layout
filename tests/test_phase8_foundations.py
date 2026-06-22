from __future__ import annotations

import numpy as np

from text_to_gds.circuit_graph import CircuitGraphBuilder, CircuitGraphEncoder
from text_to_gds.differentiable_eda import DiffCPW, DiffJunction, analytical_jpa_gain
from text_to_gds.neural_surrogate import ActiveLearningLoop, NumpySParameterPredictor
from text_to_gds.quantum_dataset import DeviceMetadata, DeviceRecord, QuantumDeviceDataset
from text_to_gds.scientific_verification import check_passivity, check_reciprocity, confidence_interval
from text_to_gds.topology_search import CircuitGenome, NoveltyScorer, patent_similarity


def test_scientific_verification_and_uncertainty():
    matrix = np.asarray([[0.1, 0.8], [0.8, 0.1]], dtype=complex)
    assert check_passivity(matrix).passed
    assert check_reciprocity(matrix).passed
    assert confidence_interval(10.0, 1.0)["lower"] < 10.0


def test_dataset_graph_and_embedding_foundations(tmp_path):
    dataset = QuantumDeviceDataset(tmp_path / "devices")
    record = DeviceRecord(metadata=DeviceMetadata(device_id="D1", device_type="JPA"))
    dataset.add_device(record)
    assert dataset.count() == 1

    graph = CircuitGraphBuilder().from_netlist({"components": [{"name": "C1", "type": "CAPACITOR", "terminals": ["a", "0"]}]})
    encoded = CircuitGraphEncoder().encode(graph)
    assert len(encoded) == 64


def test_differentiable_and_learning_foundations():
    assert DiffCPW(width=10.0, gap=6.0, length=1000.0).width > 0
    assert DiffJunction(width=0.2, height=0.25).critical_current_ua > 0
    assert analytical_jpa_gain(0.05, 2.0, 0.01, 6.0, 10.0, 50.0)["gain_db"] >= 0.0
    assert "s11_db" in NumpySParameterPredictor().predict([0.0] * 16)
    selected = ActiveLearningLoop().select_next([{"features": [1.0], "predicted": 1.0, "uncertainty": 0.5}])
    assert selected.features == [1.0]


def test_topology_novelty_and_patent_similarity():
    genome = CircuitGenome(components=["JJ", "CAPACITOR"], connections=[(0, 1)])
    assert NoveltyScorer().novelty_score(genome) == 1.0
    assert patent_similarity("quantum amplifier circuit", "quantum circuit") > 0.0
