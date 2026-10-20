import copy
import json
from pathlib import Path

import pytest

from textlayout.external.squadds_metadata_assessment import assess_metadata

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'docs/progress/evidence/2026-10-17-144536/local-packet/source/measured_device_database.json'
PACKET = ROOT / 'docs/progress/evidence/2026-10-20-042218/final-first.json'


def test_retained_real_packet_data_agreement() -> None:
    packet = json.loads(PACKET.read_text())
    before = copy.deepcopy(packet)
    result = assess_metadata(SOURCE.read_bytes(), packet)
    assert result.records_checked == 3
    assert result.evidence_status == 'PRIOR_ONLY' and not result.physics_verified
    assert packet == before


@pytest.mark.parametrize('field,value', [
    ('physics_verified', 0), ('physics_verified', True), ('helper_sha256', 'changed'),
    ('source_revision', 'main'), ('records', []), ('wm1_config_identifiers', []),
    ('contributor', {}), ('reference', {}), ('dependency_versions', {}),
    ('platform', ''), ('assessment_status', 'PASSED'), ('database_constructed', True),
])
def test_mutated_packet_rejected(field: str, value: object) -> None:
    packet = json.loads(PACKET.read_text())
    packet[field] = value
    with pytest.raises(ValueError):
        assess_metadata(SOURCE.read_bytes(), packet)


def test_changed_source_rejected() -> None:
    with pytest.raises(ValueError, match='pinned dataset'):
        assess_metadata(SOURCE.read_bytes() + b' ', json.loads(PACKET.read_text()))
