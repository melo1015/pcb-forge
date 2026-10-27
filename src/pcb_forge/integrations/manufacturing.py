"""Guarded KiCad manufacturing export helpers."""
from pathlib import Path

from pcb_forge.integrations.kicad_cli import KiCadUnavailable, run_cli
from pcb_forge.integrations.cam_preflight import validate_package


def export_manufacturing(project_dir: Path, cli_path: str, timeout: int = 120) -> dict:
    """Export Gerber layers, Excellon drill data and a STEP board model.

    KiCad CLI success is not equivalent to fabrication readiness; a human must
    inspect layer selection, drill outputs, outline, stack-up and manufacturer rules.
    """
    boards = sorted(project_dir.glob("*.kicad_pcb"))
    if not boards:
        return {"ok": False, "error": "No .kicad_pcb board found.", "outputs": []}

    root = project_dir / "manufacturing"
    outputs: list[str] = []
    commands_run: list[str] = []
    for board in boards:
        board_root = root / board.stem
        gerber_dir = board_root / "gerber"
        drill_dir = board_root / "drill"
        step_file = board_root / f"{board.stem}.step"
        gerber_dir.mkdir(parents=True, exist_ok=True)
        drill_dir.mkdir(parents=True, exist_ok=True)
        board_root.mkdir(parents=True, exist_ok=True)
        commands = [
            ("gerbers", ["pcb", "export", "gerbers", "-o", str(gerber_dir) + "/", str(board)]),
            ("drill", ["pcb", "export", "drill", "--format", "excellon", "-o", str(drill_dir), str(board)]),
            ("step", ["pcb", "export", "step", "-o", str(step_file), str(board)]),
        ]
        for label, args in commands:
            try:
                result = run_cli(cli_path, args, project_dir, timeout)
            except KiCadUnavailable as exc:
                return {"ok": False, "error": str(exc), "outputs": outputs, "commands_run": commands_run}
            commands_run.append(f"{board.name}:{label}")
            if result.returncode != 0:
                return {
                    "ok": False,
                    "error": (result.stderr or result.stdout or f"KiCad {label} export failed.")[-4000:],
                    "outputs": outputs,
                    "commands_run": commands_run,
                }
            output_dir = gerber_dir if label == "gerbers" else drill_dir if label == "drill" else None
            if output_dir is not None:
                outputs.extend(str(path) for path in output_dir.rglob("*") if path.is_file())
            elif step_file.is_file():
                outputs.append(str(step_file))

    preflight_reports = []
    for board in boards:
        board_root = root / board.stem
        report = validate_package(board_root)
        preflight_reports.append(report)
        if not report["passed"]:
            return {
                "ok": False,
                "error": "Manufacturing export completed, but structural CAM preflight failed.",
                "outputs": sorted(set(outputs)),
                "commands_run": commands_run,
                "cam_preflight": preflight_reports,
                "ready_for_manufacturing": False,
            }

    return {
        "ok": bool(outputs),
        "outputs": sorted(set(outputs)),
        "commands_run": commands_run,
        "cam_preflight": preflight_reports,
        "ready_for_manufacturing": False,
        "warning": (
            "Structural CAM preflight passed. This does not certify geometry, "
            "electrical safety, thermal performance or manufacturer-specific DFM. "
            "Review the package in an independent CAM viewer and obtain fabricator "
            "approval before ordering."
        ),
    }


def export_gerbers(project_dir: Path, cli_path: str, timeout: int = 120) -> dict:
    """Backward-compatible alias; exports the complete manufacturing set."""
    return export_manufacturing(project_dir, cli_path, timeout)
