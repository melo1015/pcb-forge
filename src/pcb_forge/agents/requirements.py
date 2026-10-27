"""Typed contract for LLM-derived electrical requirements.

The LLM may extract values from project sources, but must not invent missing
engineering requirements. Unknown values stay null and block electrical release.
"""
from __future__ import annotations

import json
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field


class ElectricalRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_voltage_min_v: float | None = Field(default=None, gt=0)
    input_voltage_nominal_v: float | None = Field(default=None, gt=0)
    input_voltage_max_v: float | None = Field(default=None, gt=0)
    output_voltage_v: float | None = Field(default=None, gt=0)
    output_current_max_a: float | None = Field(default=None, gt=0)
    ambient_temperature_max_c: float | None = None
    duty_cycle: Literal["continuous", "intermittent", "unknown"] = "unknown"
    source_type: Literal["regulated_dc", "battery", "solar", "other", "unknown"] = "unknown"
    regulator_mpn: str | None = None
    capacitor_mpn_list: list[str] = Field(default_factory=list)
    connector_current_rating_a: float | None = Field(default=None, gt=0)
    trace_copper_weight_oz: float | None = Field(default=None, gt=0)
    trace_widths_mm: list[float] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    def missing_for_electrical_review(self) -> list[str]:
        required = (
            "input_voltage_min_v",
            "input_voltage_nominal_v",
            "input_voltage_max_v",
            "output_voltage_v",
            "output_current_max_a",
            "ambient_temperature_max_c",
            "regulator_mpn",
        )
        return [name for name in required if getattr(self, name) is None]


class RequirementsAgent:
    """Turns source context into a strict data contract using an injected LLM.

    llm_call must be the project's configured LLM adapter and return a JSON string.
    Provider credentials and network clients intentionally remain outside this module.
    """

    def __init__(self, llm_call: Callable[[str], str]):
        self._llm_call = llm_call

    def extract(self, project_context: str) -> dict:
        prompt = (
            "Extract electrical requirements for a PCB design from the supplied context. "
            "Return JSON only, matching this Pydantic schema exactly: "
            + json.dumps(ElectricalRequirements.model_json_schema())
            + "\nRules: do not guess, infer typical values, or fill missing engineering "
            "requirements with defaults. Use null for unknown scalar values, empty arrays "
            "for unavailable lists, duty_cycle='unknown' and source_type='unknown' when "
            "not supported by evidence. Put source references in evidence and uncertain "
            "interpretations in assumptions. Context follows:\n"
            + project_context
        )
        raw = self._llm_call(prompt)
        try:
            requirements = ElectricalRequirements.model_validate_json(raw)
        except Exception as exc:
            raise ValueError(f"LLM returned invalid electrical-requirements JSON: {exc}") from exc
        return {
            "requirements": requirements.model_dump(),
            "missing_required_fields": requirements.missing_for_electrical_review(),
            "electrical_review_ready": not requirements.missing_for_electrical_review(),
            "release_blocked": bool(requirements.missing_for_electrical_review()),
        }
