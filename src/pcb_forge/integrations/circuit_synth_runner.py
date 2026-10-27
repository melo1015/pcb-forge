"""Execute a reviewed Circuit-Synth Python module in a separate process.

The subprocess is process-isolated, not a security sandbox. Only use trusted source.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main() -> int:
    source = Path(sys.argv[1]).resolve()
    project_dir = Path(sys.argv[2]).resolve()
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
    print(json.dumps({"status": "generated", "project_name": project_dir.name,
                      "result_type": type(result).__name__}, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ImportError, AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"CIRCUIT_SYNTH_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
