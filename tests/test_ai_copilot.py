from __future__ import annotations

from text_to_gds.ai import DesignIntent, DesignIntentParser


def test_design_intent_creation():
    intent = DesignIntent(
        device="transmon",
        parameters={"frequency_ghz": 5.0, "coupling_mhz": 100.0},
        technology="ncu_alox_2026",
        process="custom",
    )
    assert intent.device == "transmon"
    assert intent.parameters["frequency_ghz"] == 5.0
    assert intent.technology == "ncu_alox_2026"
    assert intent.process == "custom"


def test_design_intent_from_natural_language():
    parser = DesignIntentParser()
    intent = parser.parse("Design a 5 GHz transmon with 20 dB gain JPA")
    assert intent.device == "transmon"
    assert intent.parameters["frequency_ghz"] == 5.0
    assert intent.parameters["gain_db"] == 20.0


def test_design_intent_jpa_device():
    parser = DesignIntentParser()
    intent = parser.parse("Build a JPA parametric amplifier at 6 GHz")
    assert intent.device == "jpa"
    assert intent.parameters["frequency_ghz"] == 6.0


def test_design_intent_resonator_device():
    parser = DesignIntentParser()
    intent = parser.parse("Design a resonator with 500 MHz bandwidth")
    assert intent.device == "resonator"
    assert intent.parameters["bandwidth_mhz"] == 500.0


def test_design_intent_squid_device():
    parser = DesignIntentParser()
    intent = parser.parse("Create a squid device at 4 GHz")
    assert intent.device == "squid"
    assert intent.parameters["frequency_ghz"] == 4.0


def test_design_intent_unknown_device():
    parser = DesignIntentParser()
    intent = parser.parse("Design something with 10 dB gain")
    assert intent.device == "unknown"


def test_design_intent_coupling_parameter():
    parser = DesignIntentParser()
    intent = parser.parse("Design a transmon with 250 MHz coupling")
    assert intent.device == "transmon"
    assert intent.parameters["coupling_mhz"] == 250.0


def test_design_intent_to_dict():
    intent = DesignIntent(
        device="jpa",
        parameters={"frequency_ghz": 5.0},
        technology="ncu_alox_2026",
        process="alox",
    )
    d = intent.to_dict()
    assert d["device"] == "jpa"
    assert d["parameters"]["frequency_ghz"] == 5.0
    assert d["technology"] == "ncu_alox_2026"
