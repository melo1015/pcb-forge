"""Bounded orchestration for project generation and validation."""
import hashlib
import json
from pathlib import Path

from pcb_forge.agents.base import CodeGenerationAgent, DesignAgent, ValidationAgent
from pcb_forge.config import Settings
from pcb_forge.release_gate import (
    EvidenceItem,
    GateStatus,
    evaluate_pre_export_gate,
    evaluate_release_gate,
)
from pcb_forge.workspace import Workspace


class Orchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.workspace = Workspace(settings.workspace_root)
        self.design_agent = DesignAgent()
        self.codegen_agent = CodeGenerationAgent()
        self.validation_agent = ValidationAgent()

    def create_workspace(self, name: str) -> str:
        return str(self.workspace.create(name))

    @staticmethod
    def _project_fingerprint(project_dir: Path) -> str:
        """Hash design inputs, excluding reports and generated manufacturing outputs."""
        digest = hashlib.sha256()
        inputs = sorted(
            path for pattern in ("*.py", "*.kicad_sch", "*.kicad_pcb")
            for path in project_dir.rglob(pattern)
            if "manufacturing" not in path.relative_to(project_dir).parts
            and ".git" not in path.parts
            and path.name != "release_evidence.json"
        )
        for path in inputs:
            digest.update(str(path.relative_to(project_dir)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def _load_project_evidence(self, project_dir: Path) -> tuple[list[EvidenceItem], bool]:
        path = project_dir / "release_evidence.json"
        if not path.is_file():
            return [], False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("design_fingerprint") != self._project_fingerprint(project_dir):
                return [], True
            return [
                EvidenceItem.model_validate(item)
                for item in payload.get("evidence", [])
            ], False
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid project evidence file: {exc}") from exc

    def record_project_evidence(self, name: str, evidence: list[dict]) -> dict:
        """Persist project-scoped agent/tool evidence against the current design hash."""
        project_dir = self.workspace.resolve_project(name)
        items = [EvidenceItem.model_validate(item) for item in evidence]
        # Validate duplicate keys and schema before persisting anything.
        evaluate_release_gate(items)
        path = project_dir / "release_evidence.json"
        payload = {
            "design_fingerprint": self._project_fingerprint(project_dir),
            "evidence": [item.model_dump(mode="json") for item in items],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "ok": True,
            "evidence_file": str(path),
            "design_fingerprint": payload["design_fingerprint"],
            "evidence_count": len(items),
        }

    def evaluate_project_release_gate(self, name: str) -> dict:
        project_dir = self.workspace.resolve_project(name)
        evidence, stale = self._load_project_evidence(project_dir)
        report = evaluate_release_gate(evidence)
        if stale:
            report.status = GateStatus.BLOCKED
            report.ready_for_fabrication = False
            report.missing = sorted(set(report.missing + list(report.required)))
            report.notes.append(
                "Stored evidence belongs to a different design fingerprint; rerun affected checks and record fresh evidence."
            )
        report.notes.append(f"Design fingerprint: {self._project_fingerprint(project_dir)}")
        return report.model_dump(mode="json")

    def evaluate_project_pre_export_gate(self, name: str) -> dict:
        project_dir = self.workspace.resolve_project(name)
        evidence, stale = self._load_project_evidence(project_dir)
        report = evaluate_pre_export_gate(evidence)
        if stale:
            report.status = report.status.BLOCKED
            report.ready_for_fabrication = False
            report.missing = sorted(set(report.missing + list(report.required)))
            report.notes.append(
                "Stored evidence belongs to a different design fingerprint; rerun affected checks and record fresh evidence."
            )
        report.notes.append(f"Design fingerprint: {self._project_fingerprint(project_dir)}")
        return report.model_dump(mode="json")

    def generate_project(self, name: str, description: str) -> dict:
        request = self.design_agent.prepare(name, description)
        project_dir: Path = self.workspace.create(request.name)
        generation = self.codegen_agent.run(
            project_dir, request.description,
            self.settings.circuit_synth_command, self.settings.command_timeout,
        )
        validation = self.validation_agent.run(
            project_dir, self.settings.kicad_cli, self.settings.command_timeout,
        )
        gate = self.evaluate_project_release_gate(request.name)
        return {
            "project_path": str(project_dir),
            "generation": generation,
            "validation": validation.model_dump(),
            "release_gate": gate,
            "ready_for_manufacturing": False,
            "note": "Manufacturing readiness requires project-scoped evidence and external review.",
        }

    def validate_project(self, name: str) -> dict:
        project_dir = self.workspace.resolve_project(name)
        report = self.validation_agent.run(
            project_dir, self.settings.kicad_cli, self.settings.command_timeout,
        )
        result = report.model_dump()
        result["pre_export_gate"] = self.evaluate_project_pre_export_gate(name)
        result["release_gate"] = self.evaluate_project_release_gate(name)
        return result
