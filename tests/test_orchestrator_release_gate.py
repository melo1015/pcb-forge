import json
from pathlib import Path

import pytest

from pcb_forge.orchestrator import Orchestrator
from pcb_forge.release_gate import REQUIRED_PRE_EXPORT_EVIDENCE, REQUIRED_RELEASE_EVIDENCE


class FakeSettings:
    workspace_root: Path


@pytest.fixture
def orchestrator(tmp_path):
    settings = FakeSettings()
    settings.workspace_root = tmp_path
    instance = Orchestrator.__new__(Orchestrator)
    instance.settings = settings
    from pcb_forge.workspace import Workspace
    instance.workspace = Workspace(settings.workspace_root)
    return instance


def _project(orchestrator, tmp_path):
    project = Path(orchestrator.create_workspace("demo"))
    (project / "design.kicad_pcb").write_text("design rev A", encoding="utf-8")
    return project


def _evidence(keys):
    return [
        {"key": key, "passed": True, "source": "test", "artifact": f"evidence/{key}.json"}
        for key in keys
    ]


def test_project_gate_blocks_without_evidence(orchestrator, tmp_path):
    _project(orchestrator, tmp_path)
    report = orchestrator.evaluate_project_release_gate("demo")
    assert report["status"] == "BLOCKED"
    assert report["ready_for_fabrication"] is False


def test_evidence_is_bound_to_design_fingerprint(orchestrator, tmp_path):
    project = _project(orchestrator, tmp_path)
    orchestrator.record_project_evidence("demo", _evidence(REQUIRED_RELEASE_EVIDENCE))
    assert orchestrator.evaluate_project_release_gate("demo")["status"] == "PASS"

    (project / "design.kicad_pcb").write_text("design rev B", encoding="utf-8")
    report = orchestrator.evaluate_project_release_gate("demo")
    assert report["status"] == "BLOCKED"
    assert any("different design fingerprint" in note for note in report["notes"])


def test_pre_export_gate_uses_only_pre_export_evidence(orchestrator, tmp_path):
    _project(orchestrator, tmp_path)
    orchestrator.record_project_evidence("demo", _evidence(REQUIRED_PRE_EXPORT_EVIDENCE))
    report = orchestrator.evaluate_project_pre_export_gate("demo")
    assert report["status"] == "PASS"
    assert report["ready_for_fabrication"] is False


def test_record_evidence_rejects_duplicate_keys(orchestrator, tmp_path):
    _project(orchestrator, tmp_path)
    evidence = _evidence(REQUIRED_RELEASE_EVIDENCE)
    evidence.append(evidence[0])
    with pytest.raises(ValueError, match="Duplicate evidence key"):
        orchestrator.record_project_evidence("demo", evidence)
