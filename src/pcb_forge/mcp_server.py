"""MCP entry point."""
import logging

from mcp.server.fastmcp import FastMCP

from pcb_forge.config import Settings
from pcb_forge.orchestrator import Orchestrator

settings = Settings.from_env()
orchestrator = Orchestrator(settings)
mcp = FastMCP("pcb-forge")


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
        logging.exception("Project generation failed")
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def pcb_validate_project(name: str) -> dict:
    """Run configured KiCad ERC/DRC checks for an existing workspace."""
    try:
        return {"ok": True, "report": orchestrator.validate_project(name)}
    except Exception as exc:
        logging.exception("Project validation failed")
        return {"ok": False, "error": str(exc)}


def main() -> None:
    logging.basicConfig(level=settings.log_level)
    mcp.run()
