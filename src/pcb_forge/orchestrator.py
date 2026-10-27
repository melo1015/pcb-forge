"""Bounded orchestration for project generation and validation."""
from pathlib import Path

from pcb_forge.agents.base import CodeGenerationAgent, DesignAgent, ValidationAgent
from pcb_forge.config import Settings
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
        return {
            "project_path": str(project_dir),
            "generation": generation,
            "validation": validation.model_dump(),
            "ready_for_manufacturing": False,
            "note": "Manufacturing readiness requires successful checks and human review.",
        }

    def validate_project(self, name: str) -> dict:
        project_dir = self.workspace.resolve_project(name)
        report = self.validation_agent.run(
            project_dir, self.settings.kicad_cli, self.settings.command_timeout,
        )
        return report.model_dump()
