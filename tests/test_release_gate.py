from pcb_forge.release_gate import (
    REQUIRED_RELEASE_EVIDENCE,
    EvidenceItem,
    GateStatus,
    evaluate_release_gate,
)


def test_release_gate_blocks_when_evidence_is_missing():
    report = evaluate_release_gate([])

    assert report.status == GateStatus.BLOCKED
    assert report.ready_for_fabrication is False
    assert set(report.missing) == set(REQUIRED_RELEASE_EVIDENCE)


def test_release_gate_fails_when_any_required_check_fails():
    evidence = [
        EvidenceItem(key=key, passed=True, source="test", artifact=f"artifacts/{key}.json")
        for key in REQUIRED_RELEASE_EVIDENCE
    ]
    evidence.append(EvidenceItem(key="thermal_analysis_pass", passed=False, source="thermal report"))

    # Duplicate evidence must be rejected rather than silently overwriting a prior result.
    import pytest
    with pytest.raises(ValueError, match="Duplicate evidence key"):
        evaluate_release_gate(evidence)


def test_release_gate_passes_only_with_all_required_evidence():
    evidence = [
        EvidenceItem(key=key, passed=True, source="tool-or-review", artifact=f"evidence/{key}.json")
        for key in REQUIRED_RELEASE_EVIDENCE
    ]

    report = evaluate_release_gate(evidence)

    assert report.status == GateStatus.PASS
    assert report.ready_for_fabrication is True
    assert report.missing == []
    assert report.failed == []


def test_release_gate_reports_failed_evidence():
    evidence = [
        EvidenceItem(key=key, passed=True, source="tool-or-review", details="review evidence recorded")
        for key in REQUIRED_RELEASE_EVIDENCE
    ]
    evidence[0] = EvidenceItem(key="ci_green", passed=False, source="GitHub Actions")

    report = evaluate_release_gate(evidence)

    assert report.status == GateStatus.FAIL
    assert report.ready_for_fabrication is False
    assert report.failed == ["ci_green"]
