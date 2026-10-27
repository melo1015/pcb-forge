import json

import pytest

from pcb_forge.agents.requirements import RequirementsAgent


def test_requirements_agent_blocks_release_when_critical_values_are_unknown():
    payload = {
        "input_voltage_min_v": None,
        "input_voltage_nominal_v": None,
        "input_voltage_max_v": None,
        "output_voltage_v": 5,
        "output_current_max_a": None,
        "ambient_temperature_max_c": None,
        "duty_cycle": "unknown",
        "source_type": "unknown",
        "regulator_mpn": None,
        "capacitor_mpn_list": [],
        "connector_current_rating_a": None,
        "trace_copper_weight_oz": None,
        "trace_widths_mm": [],
        "evidence": [],
        "assumptions": [],
    }
    agent = RequirementsAgent(lambda prompt: json.dumps(payload))

    result = agent.extract("Reference regulator circuit, exact input/load unspecified")

    assert result["release_blocked"] is True
    assert result["electrical_review_ready"] is False
    assert "input_voltage_max_v" in result["missing_required_fields"]
    assert "output_current_max_a" in result["missing_required_fields"]


def test_requirements_agent_accepts_complete_review_inputs():
    payload = {
        "input_voltage_min_v": 9,
        "input_voltage_nominal_v": 12,
        "input_voltage_max_v": 15,
        "output_voltage_v": 5,
        "output_current_max_a": 0.1,
        "ambient_temperature_max_c": 40,
        "duty_cycle": "continuous",
        "source_type": "regulated_dc",
        "regulator_mpn": "L7805CV",
        "capacitor_mpn_list": ["example-capacitor-1", "example-capacitor-2"],
        "connector_current_rating_a": 0.5,
        "trace_copper_weight_oz": 1,
        "trace_widths_mm": [0.5, 0.5],
        "evidence": ["user-approved design specification"],
        "assumptions": [],
    }
    agent = RequirementsAgent(lambda prompt: json.dumps(payload))

    result = agent.extract("Design spec: 9-15 V input, 5 V/100 mA output")

    assert result["release_blocked"] is False
    assert result["electrical_review_ready"] is True
    assert result["missing_required_fields"] == []


def test_requirements_agent_rejects_invalid_llm_json():
    agent = RequirementsAgent(lambda prompt: "not json")

    with pytest.raises(ValueError, match="invalid electrical-requirements JSON"):
        agent.extract("circuit context")
