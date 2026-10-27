import pytest

from pcb_forge.agents.base import DesignAgent


def test_design_agent_normalizes_whitespace():
    request = DesignAgent().prepare("demo_board", "  5V   regulator with input protection  ")
    assert request.description == "5V regulator with input protection"


def test_design_agent_rejects_too_short_description():
    with pytest.raises(ValueError):
        DesignAgent().prepare("demo", "short")
