"""Manual E2E check against an installed Circuit-Synth and KiCad CLI."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pcb_forge.integrations.circuit_synth import generate_from_source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Trusted Circuit-Synth Python source")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pcb-forge-e2e-artifacts"),
        help="Directory to retain generated project and ERC/DRC reports",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        print(f"Source not found: {source}", file=sys.stderr)
        return 2

    cli = shutil.which("kicad-cli")
    if not cli:
        print("kicad-cli is required on the E2E runner", file=sys.stderr)
        return 2

    output_dir = args.output_dir.resolve()
    project_dir = output_dir / "regulator_5v"
    output_dir.mkdir(parents=True, exist_ok=True)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True)
    local_source = project_dir / source.name
    shutil.copy2(source, local_source)

    result = generate_from_source(project_dir, local_source, timeout=600)
    print(json.dumps(result, indent=2, default=str))
    if not result["ok"]:
        print("Circuit-Synth generation failed or produced no KiCad files.", file=sys.stderr)
        return 1

    schematics = sorted(project_dir.rglob("*.kicad_sch"))
    boards = sorted(project_dir.rglob("*.kicad_pcb"))
    if not schematics or not boards:
        print("E2E requires at least one .kicad_sch and one .kicad_pcb.", file=sys.stderr)
        return 1

    reports = []
    for kind, files, command_prefix, suffix in (
        ("ERC", schematics, ["sch", "erc"], ".erc.rpt"),
        ("DRC", boards, ["pcb", "drc"], ".drc.rpt"),
    ):
        for design_file in files:
            report = design_file.with_suffix(suffix)
            command = [cli, *command_prefix, "-o", str(report), str(design_file)]
            try:
                completed = subprocess.run(
                    command, capture_output=True, text=True, timeout=180, check=False
                )
                item = {
                    "kind": kind,
                    "file": str(design_file),
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-4000:],
                    "stderr": completed.stderr[-4000:],
                    "report": str(report),
                    "report_exists": report.is_file(),
                }
            except subprocess.TimeoutExpired as exc:
                item = {
                    "kind": kind,
                    "file": str(design_file),
                    "returncode": 124,
                    "stdout": str(exc.stdout or "")[-4000:],
                    "stderr": f"KiCad {kind} timed out after 180 seconds",
                    "report": str(report),
                    "report_exists": report.is_file(),
                }
            reports.append(item)

    summary = {
        "generation": result,
        "validation_commands": reports,
        "schematics": [str(path) for path in schematics],
        "boards": [str(path) for path in boards],
        "note": (
            "A zero CLI return code does not prove the design is violation-free; "
            "inspect the retained ERC/DRC reports."
        ),
    }
    summary_path = output_dir / "e2e-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))

    if any(item["returncode"] != 0 for item in reports):
        return 1
    if any(not item["report_exists"] for item in reports):
        print("One or more ERC/DRC reports were not created.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
