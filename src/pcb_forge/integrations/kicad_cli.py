"""KiCad CLI adapter with timeout and no shell expansion."""
import subprocess
from pathlib import Path

from pcb_forge.models import Diagnostic, ValidationReport


class KiCadUnavailable(RuntimeError):
    pass


def run_cli(cli_path: str, args: list[str], project_dir: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    if not cli_path:
        raise KiCadUnavailable("KiCad CLI is not configured; set PCB_FORGE_KICAD_CLI.")
    try:
        return subprocess.run(
            [cli_path, *args],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise KiCadUnavailable(f"KiCad CLI failed to execute: {exc}") from exc


def validate_project(project_dir: Path, cli_path: str, timeout: int = 120) -> ValidationReport:
    boards = list(project_dir.glob("*.kicad_pcb"))
    schematics = list(project_dir.glob("*.kicad_sch"))
    diagnostics: list[Diagnostic] = []
    checks: list[str] = []
    if not boards:
        diagnostics.append(Diagnostic(code="PCB_MISSING", message="No .kicad_pcb board found."))
    if not schematics:
        diagnostics.append(Diagnostic(code="SCHEMATIC_MISSING", message="No .kicad_sch schematic found."))
    if not cli_path:
        diagnostics.append(Diagnostic(code="KICAD_NOT_CONFIGURED", message="KiCad CLI is not configured."))
        return ValidationReport(project_path=str(project_dir), checks_run=checks, diagnostics=diagnostics, passed=False)
    for board in boards:
        result = run_cli(cli_path, ["pcb", "drc", "--exit-code-violations", str(board)], project_dir, timeout)
        checks.append(f"DRC:{board.name}")
        if result.returncode != 0:
            diagnostics.append(Diagnostic(
                code="DRC_FAILED",
                message=(result.stderr or result.stdout or "KiCad DRC returned non-zero status.")[-4000:],
                path=str(board),
            ))
    for schematic in schematics:
        result = run_cli(cli_path, ["sch", "erc", "--exit-code-violations", str(schematic)], project_dir, timeout)
        checks.append(f"ERC:{schematic.name}")
        if result.returncode != 0:
            diagnostics.append(Diagnostic(
                code="ERC_FAILED",
                message=(result.stderr or result.stdout or "KiCad ERC returned non-zero status.")[-4000:],
                path=str(schematic),
            ))
    return ValidationReport(
        project_path=str(project_dir),
        checks_run=checks,
        diagnostics=diagnostics,
        passed=bool(boards and schematics and checks) and not diagnostics,
        notes=["ERC/DRC coverage depends on the installed KiCad version and project format."],
    )
