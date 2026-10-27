"""Explicit adapter boundary for circuit-synth.

Do not assume a Python API here: circuit-synth versions and entry points must be
verified in the target environment. The configured command is treated as an
executable path plus fixed arguments; user prompts are written to a file and
are not interpolated into a shell command.
"""
from pathlib import Path
import shlex
import subprocess


class IntegrationUnavailable(RuntimeError):
    pass


def generate(project_dir: Path, prompt: str, command: str, timeout: int = 120) -> dict:
    if not command:
        raise IntegrationUnavailable(
            "circuit-synth command is not configured; set PCB_FORGE_CIRCUIT_SYNTH_COMMAND."
        )
    project_dir.mkdir(parents=True, exist_ok=True)
    request_file = project_dir / "design_request.txt"
    request_file.write_text(prompt.strip() + "\n", encoding="utf-8")
    argv = shlex.split(command)
    if not argv:
        raise IntegrationUnavailable("Configured circuit-synth command is empty.")
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
        raise IntegrationUnavailable(f"Could not run circuit-synth adapter: {exc}") from exc
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
        "request_file": str(request_file),
    }
