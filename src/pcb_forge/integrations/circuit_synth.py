"""Adapter for a configured external circuit-generation command.

This is deliberately not a direct Circuit-Synth CLI integration: upstream
Circuit-Synth exposes a Python circuit API and does not define the generic
``--request-file/--output-dir`` command contract used here. Configure this
setting with a trusted wrapper executable that implements that contract, or
replace this adapter with a version-specific integration.
"""
import shlex
import subprocess
from pathlib import Path


class IntegrationUnavailable(RuntimeError):
    """Raised when the external generation adapter cannot be run."""


def generate(project_dir: Path, prompt: str, command: str, timeout: int = 120) -> dict:
    if not command:
        raise IntegrationUnavailable(
            "No generation adapter configured. Set PCB_FORGE_CIRCUIT_SYNTH_COMMAND "
            "to a trusted wrapper implementing --request-file and --output-dir."
        )
    project_dir.mkdir(parents=True, exist_ok=True)
    request_file = project_dir / "design_request.txt"
    request_file.write_text(prompt.strip() + "\n", encoding="utf-8")
    argv = shlex.split(command)
    if not argv:
        raise IntegrationUnavailable("Configured generation adapter command is empty.")
    try:
        completed = subprocess.run(
            argv + ["--request-file", str(request_file), "--output-dir", str(project_dir)],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IntegrationUnavailable(f"Could not run generation adapter: {exc}") from exc
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
        "request_file": str(request_file),
        "adapter_contract": "external-wrapper-v1",
        "generated_files_detected": sorted(
            str(path) for path in project_dir.glob("*.kicad*") if path.is_file()
        ),
    }



def generate_from_source(
    project_dir: Path, source_file: Path, timeout: int = 120, python_executable: str | None = None
) -> dict:
    """Generate KiCad files from a reviewed Circuit-Synth Python module.

    The source must be inside project_dir and expose build_circuit(), returning an
    object with generate_kicad_project(project_name). This is not a sandbox: only
    execute source code that has been reviewed and explicitly trusted.
    """
    import sys

    project_dir = project_dir.resolve()
    source_file = source_file.resolve()
    try:
        source_file.relative_to(project_dir)
    except ValueError as exc:
        raise IntegrationUnavailable(
            "Circuit-Synth source must be located inside the project workspace."
        ) from exc
    if not source_file.is_file() or source_file.suffix != ".py":
        raise IntegrationUnavailable("Circuit-Synth source must be an existing .py file.")
    runner = Path(__file__).with_name("circuit_synth_runner.py")
    command = [
        python_executable or sys.executable,
        str(runner),
        str(source_file),
        str(project_dir),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IntegrationUnavailable(f"Could not run Circuit-Synth source: {exc}") from exc
    generated = sorted(
        str(path) for path in project_dir.glob("*.kicad*") if path.is_file()
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
        "adapter_contract": "circuit-synth-python-module-v1",
        "source_file": str(source_file),
        "generated_files_detected": generated,
        "ok": completed.returncode == 0 and bool(generated),
    }
