"""Agent contracts kept deterministic and testable."""
from dataclasses import dataclass


@dataclass
class DesignRequest:
    name: str
    description: str


class DesignAgent:
    """Normalizes and checks a user request before generation."""

    def prepare(self, name: str, description: str) -> DesignRequest:
        cleaned = " ".join(description.split())
        if len(cleaned) < 12:
            raise ValueError("Describe the circuit in at least 12 characters.")
        return DesignRequest(name=name, description=cleaned)


class CodeGenerationAgent:
    """Delegates code/project generation to the configured circuit-synth adapter."""

    def run(self, project_dir, description, command, timeout):
        from pcb_forge.integrations.circuit_synth import generate
        return generate(project_dir, description, command, timeout)


class ValidationAgent:
    """Runs the available KiCad checks."""

    def run(self, project_dir, cli_path, timeout):
        from pcb_forge.integrations.kicad_cli import validate_project
        return validate_project(project_dir, cli_path, timeout)


class CorrectionAgent:
    """Produces bounded, human-reviewable correction guidance.

    Automatic source rewriting is intentionally not enabled until generated code
    has a sandbox and a deterministic patch contract.
    """

    def propose(self, diagnostics):
        return {
            "automatic_patch_applied": False,
            "diagnostics": [d.model_dump() for d in diagnostics],
            "next_step": "Review diagnostics and apply a minimal patch in an isolated environment.",
        }
