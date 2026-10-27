"""Execute a reviewed Circuit-Synth Python module in a separate process.

The subprocess is process-isolated, not a security sandbox. Only use trusted source.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _remove_adapter_directory_from_import_path() -> None:
    """Prevent this adapter's sibling circuit_synth.py from shadowing the dependency.

    When Python executes this file directly, sys.path[0] is the directory that
    contains the adapter module. That directory also contains pcb_forge's
    circuit_synth.py integration adapter, which would otherwise mask the
    installed upstream `circuit_synth` package imported by user circuit files.
    """
    adapter_dir = Path(__file__).resolve().parent
    sys.path[:] = [
        entry
        for entry in sys.path
        if not entry or Path(entry).resolve() != adapter_dir
    ]


def main() -> int:
    source = Path(sys.argv[1]).resolve()
    project_dir = Path(sys.argv[2]).resolve()
    _remove_adapter_directory_from_import_path()

    spec = importlib.util.spec_from_file_location("pcb_forge_user_circuit", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load circuit module: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build_circuit = getattr(module, "build_circuit", None)
    if not callable(build_circuit):
        raise TypeError("Circuit module must expose build_circuit()")
    circuit = build_circuit()
    generate = getattr(circuit, "generate_kicad_project", None)
    if not callable(generate):
        raise TypeError("build_circuit() must return an object with generate_kicad_project()")
    result = generate(project_dir.name)
    print(
        json.dumps(
            {
                "status": "generated",
                "project_name": project_dir.name,
                "result_type": type(result).__name__,
            },
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"CIRCUIT_SYNTH_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
