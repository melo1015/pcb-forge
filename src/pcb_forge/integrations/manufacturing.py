"""Guarded KiCad manufacturing export helpers."""
from pathlib import Path

from pcb_forge.integrations.kicad_cli import KiCadUnavailable, run_cli
from pcb_forge.models import Diagnostic


def export_gerbers(project_dir: Path, cli_path: str, timeout: int = 120) -> dict:
    boards = list(project_dir.glob("*.kicad_pcb"))
    if not boards:
        return {"ok": False, "error": "No .kicad_pcb board found."}
    output_dir = project_dir / "manufacturing" / "gerber"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for board in boards:
        try:
            result = run_cli(cli_path, ["pcb", "export", "gerbers", "-o", str(output_dir) + "/", str(board)], project_dir, timeout)
        except KiCadUnavailable as exc:
            return {"ok": False, "error": str(exc), "outputs": outputs}
        if result.returncode != 0:
            return {"ok": False, "error": (result.stderr or result.stdout)[-4000:], "outputs": outputs}
        outputs.extend(str(p) for p in output_dir.iterdir() if p.is_file())
    return {"ok": bool(outputs), "outputs": sorted(set(outputs)), "warning": "Verify layer selection, drill files, board outline and manufacturer rules before ordering."}
