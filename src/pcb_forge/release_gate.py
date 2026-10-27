"""Evidence-based release gates for multi-agent PCB review.

LLM agents may propose findings, but only recorded evidence can satisfy a gate.
Missing evidence is BLOCKED, never silently treated as a pass.
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class EvidenceItem(BaseModel):
    key: str
    passed: bool | None = None
    source: str | None = None
    artifact: str | None = None
    details: str | None = None


class ReleaseGateReport(BaseModel):
    status: GateStatus
    ready_for_fabrication: bool = False
    required: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# Keep these keys stable: agents and the orchestrator use them as a contract.
REQUIRED_RELEASE_EVIDENCE = (
    "ci_green",
    "erc_pass",
    "drc_pass",
    "fabrication_package_structural_pass",
    "independent_cam_review_pass",
    "electrical_requirements_complete",
    "component_datasheets_reviewed",
    "thermal_analysis_pass",
    "fabricator_rules_confirmed",
)


def evaluate_release_gate(evidence: list[EvidenceItem]) -> ReleaseGateReport:
    """Evaluate release readiness from auditable evidence, not LLM assertions."""
    by_key: dict[str, EvidenceItem] = {}
    for item in evidence:
        if item.key in by_key:
            raise ValueError(f"Duplicate evidence key: {item.key}")
        by_key[item.key] = item

    missing = [
        key for key in REQUIRED_RELEASE_EVIDENCE
        if key not in by_key or by_key[key].passed is None
    ]
    failed = [
        key for key in REQUIRED_RELEASE_EVIDENCE
        if key in by_key and by_key[key].passed is False
    ]

    if failed:
        status = GateStatus.FAIL
    elif missing:
        status = GateStatus.BLOCKED
    else:
        status = GateStatus.PASS

    notes = [
        "LLM-generated summaries are not proof by themselves; evidence must reference a tool result, artifact, datasheet, or recorded review.",
        "Prototype electrical testing and assembly/fabricator sign-off remain project-specific release activities where applicable.",
    ]
    return ReleaseGateReport(
        status=status,
        ready_for_fabrication=status == GateStatus.PASS,
        required=list(REQUIRED_RELEASE_EVIDENCE),
        missing=missing,
        failed=failed,
        evidence=evidence,
        notes=notes,
    )
