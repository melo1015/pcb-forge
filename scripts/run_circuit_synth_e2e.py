"""Manual E2E check against an installed Circuit-Synth and KiCad CLI."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pcb_forge.integrations.circuit_synth import generate_from_source


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/run_circuit_synth_e2e.py SOURCE.py", file=sys.stderr)
        return 2

    source = Path(sys.argv[1]).resolve()
    if not source.is_file():
        print(f"Source not found: {source}", file=sys.stderr)
        return 2

    cli = shutil.which("kicad-cli")
    if not cli:
        print("kicad-cli is required on the E2E runner", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="pcb-forge-e2e-") as temp:
        workspace = Path(temp) / "regulator_5v"
        workspace.mkdir()
        local_source = workspace / source.name
        shutil.copy2(source, local_source)

        result = generate_from_source(workspace, local_source, timeout=600)
        print(json.dumps(result, indent=2, default=str))
        if not result["ok"]:
            print("Circuit-Synth generation failed or produced no KiCad files.", file=sys.stderr)
            return 1

        schematics = sorted(workspace.rglob("*.kicad_sch"))
        boards = sorted(workspace.rglob("*.kicad_pcb"))
        if not schematics or not boards:
            print("E2E requires at least one .kicad_sch and one .kicad_pcb.", file=sys.stderr)
            return 1

        reports = []
        for schematic in schematics:
            report = schematic.with_suffix(".erc.rpt")
            command = [cli, "sch", "erc", "-o", str(report), str(schematic)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
            reports.append({
                "kind": "ERC",
                "file": str(schematic),
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "report": str(report),
            })
        for board in boards:
            report = board.with_suffix(".drc.rpt")
            command = [cli, "pcb", "drc", "-o", str(report), str(board)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
            reports.append({
                "kind": "DRC",
                "file": str(board),
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "report": str(report),
            })

        print(json.dumps({"validation_commands": reports}, indent=2))
        # KiCad versions may return zero despite reported violations. Preserve
        # reports as CI artifacts and fail on CLI execution errors, not findings.
        if any(item["returncode"] != 0 for item in reports):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
