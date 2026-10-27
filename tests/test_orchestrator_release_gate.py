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


def _evidence(keys, project):
    evidence_dir = project / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    items = []
    for key in keys:
        artifact = evidence_dir / f"{key}.json"
        artifact.write_text(
            __import__("json").dumps({"check": key, "passed": True}),
            encoding="utf-8",
        )
        items.append({
            "key": key,
            "passed": True,
            "source": "test-tool",
            "artifact": str(artifact.relative_to(project)),
        })
    return items


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
    project = _project(orchestrator, tmp_path)
    orchestrator.record_project_evidence("demo", _evidence(REQUIRED_PRE_EXPORT_EVIDENCE, project))
    report = orchestrator.evaluate_project_pre_export_gate("demo")
    assert report["status"] == "PASS"
    assert report["ready_for_fabrication"] is False


def test_record_evidence_rejects_duplicate_keys(orchestrator, tmp_path):
    project = _project(orchestrator, tmp_path)
    evidence = _evidence(REQUIRED_RELEASE_EVIDENCE, project)
    evidence.append(evidence[0])
    with pytest.raises(ValueError, match="Duplicate evidence key"):
        orchestrator.record_project_evidence("demo", evidence)



def test_record_evidence_rejects_missing_artifact(orchestrator, tmp_path):
    _project(orchestrator, tmp_path)
    evidence = [{
        "key": "erc_pass",
        "passed": True,
        "source": "kicad-cli",
        "artifact": "reports/erc.json",
    }]
    with pytest.raises(ValueError, match="artifact does not exist"):
        orchestrator.record_project_evidence("demo", evidence)


def test_record_evidence_rejects_artifact_path_escape(orchestrator, tmp_path):
    _project(orchestrator, tmp_path)
    evidence = [{
        "key": "erc_pass",
        "passed": True,
        "source": "kicad-cli",
        "artifact": "../outside.json",
    }]
    with pytest.raises(ValueError, match="inside the project workspace"):
        orchestrator.record_project_evidence("demo", evidence)


def test_record_evidence_rejects_non_https_url(orchestrator, tmp_path):
    _project(orchestrator, tmp_path)
    evidence = [{
        "key": "ci_green",
        "passed": True,
        "source": "github-actions",
        "artifact": "http://example.test/run/1",
    }]
    with pytest.raises(ValueError, match="must use HTTPS"):
        orchestrator.record_project_evidence("demo", evidence)


def test_human_review_requires_explicit_source_and_details(orchestrator, tmp_path):
    _project(orchestrator, tmp_path)
    evidence = [{
        "key": "independent_cam_review_pass",
        "passed": True,
        "source": "human_review:reviewer@example.invalid",
        "details": "Reviewed exported Gerbers in independent CAM viewer; notes archived.",
    }]
    result = orchestrator.record_project_evidence("demo", evidence)
    assert result["ok"] is True
