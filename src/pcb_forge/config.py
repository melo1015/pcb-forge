"""Environment-backed configuration for PCB Forge."""
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    workspace_root: Path
    kicad_cli: str
    circuit_synth_command: str
    max_correction_cycles: int = 5
    command_timeout: int = 120
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        cycles = _positive_int("PCB_FORGE_MAX_CORRECTION_CYCLES", 5)
        timeout = _positive_int("PCB_FORGE_COMMAND_TIMEOUT", 120)
        return cls(
            workspace_root=Path(os.getenv("PCB_FORGE_WORKSPACE", "./.workspace")).resolve(),
            kicad_cli=os.getenv("PCB_FORGE_KICAD_CLI", "").strip(),
            circuit_synth_command=os.getenv("PCB_FORGE_CIRCUIT_SYNTH_COMMAND", "").strip(),
            max_correction_cycles=min(cycles, 5),
            command_timeout=timeout,
            log_level=os.getenv("PCB_FORGE_LOG_LEVEL", "INFO").upper(),
        )


def _positive_int(key: str, default: int) -> int:
    try:
        value = int(os.getenv(key, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default
