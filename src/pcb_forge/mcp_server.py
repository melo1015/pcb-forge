"""MCP entry point."""
import logging

from mcp.server.fastmcp import FastMCP

from pcb_forge.config import Settings
from pcb_forge.integrations.circuit_synth import generate_from_source
from pcb_forge.integrations.manufacturing import export_manufacturing
from pcb_forge.orchestrator import Orchestrator
from pcb_forge.release_gate import EvidenceItem, evaluate_release_gate


settings = Settings.from_env()
orchestrator = Orchestrator(settings)
mcp = FastMCP("pcb-forge")
logger = logging.getLogger(__name__)


@mcp.tool()
def pcb_create_workspace(name: str) -> dict:
    """Create a project workspace using a safe project name."""
    try:
        return {"ok": True, "path": orchestrator.create_workspace(name)}
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def pcb_generate_project(name: str, description: str) -> dict:
    """Generate a circuit project and run configured validation tools."""
    try:
        return {"ok": True, "result": orchestrator.generate_project(name, description)}
    except Exception as exc:
        logger.exception("Project generation failed")
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def pcb_generate_from_circuit_synth_source(name: str, source_filename: str) -> dict:
    """Generate a KiCad project from a reviewed Python Circuit-Synth module in the workspace.

    The source must be trusted code, located inside the named project's workspace,
    and expose build_circuit() returning a Circuit-Synth object.
    """
    try:
        project_dir = orchestrator.workspace.resolve_project(name)
        source_file = (project_dir / source_filename).resolve()
        source_file.relative_to(project_dir.resolve())
        result = generate_from_source(
            project_dir, source_file, settings.command_timeout
        )
        return {"ok": bool(result["ok"]), "result": result}
    except Exception as exc:
        logger.exception("Circuit-Synth source generation failed")
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def pcb_validate_project(name: str) -> dict:
    """Run configured KiCad ERC/DRC checks for an existing workspace."""
    try:
        return {"ok": True, "report": orchestrator.validate_project(name)}
    except Exception as exc:
        logger.exception("Project validation failed")
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def pcb_evaluate_release_gate(evidence: list[dict]) -> dict:
    """Evaluate fabrication release from auditable evidence supplied by specialized agents.

    Each evidence item must contain a stable key, a boolean passed value (or null if
    unknown), and traceability for any claimed pass. Missing evidence blocks release.
    """
    try:
        items = [EvidenceItem.model_validate(item) for item in evidence]
        report = evaluate_release_gate(items)
        return {"ok": True, "report": report.model_dump(mode="json")}
    except Exception as exc:
        logger.exception("Release gate evaluation failed")
        return {"ok": False, "error": str(exc), "ready_for_fabrication": False}


@mcp.tool()
def pcb_export_manufacturing(name: str) -> dict:
    """Export Gerber, Excellon drill and STEP files after ERC/DRC; human review required."""
    try:
        project_dir = orchestrator.workspace.resolve_project(name)
        report = orchestrator.validate_project(name)
        if not report.get("passed"):
            return {
                "ok": False,
                "error": "Validation did not pass; manufacturing export was blocked.",
                "validation": report,
            }
        return export_manufacturing(project_dir, settings.kicad_cli, settings.command_timeout)
    except Exception as exc:
        logger.exception("Manufacturing export failed")
        return {"ok": False, "error": str(exc)}


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    mcp.run()
