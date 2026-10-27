"""Evidence-based release gates for multi-agent PCB review.

LLM agents may propose findings, but only recorded evidence can satisfy a gate.
Missing evidence is BLOCKED, never silently treated as a pass.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def successful_evidence_must_be_traceable(self) -> EvidenceItem:
        if self.passed is True and (
            not self.source or not (self.artifact or self.details)
        ):
            raise ValueError(
                "Passing evidence requires a source and an artifact or review details."
            )
        return self


class ReleaseGateReport(BaseModel):
    status: GateStatus
    ready_for_fabrication: bool = False
    required: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# Stable contract shared by specialized agents and the orchestrator.
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

# Evidence that must exist before exporting a manufacturing package.
# Structural CAM preflight and independent CAM review necessarily happen after export.
REQUIRED_PRE_EXPORT_EVIDENCE = (
    "ci_green",
    "erc_pass",
    "drc_pass",
    "electrical_requirements_complete",
    "component_datasheets_reviewed",
    "thermal_analysis_pass",
    "fabricator_rules_confirmed",
)


def evaluate_evidence_gate(
    evidence: list[EvidenceItem], required: tuple[str, ...], *, gate_name: str
) -> ReleaseGateReport:
    by_key: dict[str, EvidenceItem] = {}
    for item in evidence:
        if item.key in by_key:
            raise ValueError(f"Duplicate evidence key: {item.key}")
        by_key[item.key] = item

    missing = [
        key for key in required
        if key not in by_key or by_key[key].passed is None
    ]
    failed = [
        key for key in required
        if key in by_key and by_key[key].passed is False
    ]

    if failed:
        status = GateStatus.FAIL
    elif missing:
        status = GateStatus.BLOCKED
    else:
        status = GateStatus.PASS

    return ReleaseGateReport(
        status=status,
        ready_for_fabrication=status == GateStatus.PASS and gate_name == "release",
        required=list(required),
        missing=missing,
        failed=failed,
        evidence=evidence,
        notes=[
            f"Gate: {gate_name}.",
            "LLM-generated summaries are not proof by themselves; evidence must reference a tool result, artifact, datasheet, or recorded review.",
            "Prototype electrical testing and assembly/fabricator sign-off remain project-specific release activities where applicable.",
        ],
    )


def evaluate_release_gate(evidence: list[EvidenceItem]) -> ReleaseGateReport:
    """Evaluate final fabrication readiness from auditable evidence."""
    return evaluate_evidence_gate(
        evidence, REQUIRED_RELEASE_EVIDENCE, gate_name="release"
    )


def evaluate_pre_export_gate(evidence: list[EvidenceItem]) -> ReleaseGateReport:
    """Evaluate whether the manufacturing package may be generated."""
    return evaluate_evidence_gate(
        evidence, REQUIRED_PRE_EXPORT_EVIDENCE, gate_name="pre-export"
    )
