"""Manual E2E check against an installed Circuit-Synth and KiCad CLI."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pcb_forge.integrations.circuit_synth import IntegrationUnavailable, generate_from_source


def _create_pcb_seed(schematic: Path, board: Path, cli: str) -> dict[str, object]:
    """Use KiCad's netlist and pcbnew when Circuit-Synth lacks PCB generation."""
    helper = Path(__file__).resolve().with_name("create_board_from_netlist.py")
    system_python = shutil.which("python3")
    candidates = [Path("/usr/bin/python3"), Path(system_python) if system_python else None]
    python = next(
        (
            str(candidate)
            for candidate in candidates
            if candidate and candidate.is_file()
            and subprocess.run(
                [str(candidate), "-c", "import pcbnew"],
                capture_output=True, text=True, timeout=20, check=False,
            ).returncode == 0
        ),
        None,
    )
    if python is None:
        return {
            "ok": False,
            "error": "KiCad pcbnew Python bindings unavailable; install KiCad with pcbnew bindings.",
        }
    command = [
        python, str(helper), "--schematic", str(schematic),
        "--board", str(board), "--kicad-cli", cli,
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=180, check=False
    )
    return {
        "ok": completed.returncode == 0 and board.is_file(),
        "mode": "kicad-netlist-pcbnew-placement-seed",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "board": str(board),
        "warning": (
            "Fallback PCB is an unrouted placement seed. It is not a production "
            "layout and must be reviewed/routed before manufacturing."
        ),
    }


def _route_reference_pcb(board: Path) -> dict[str, object]:
    """Apply guarded, design-specific routing to the reference fallback board."""
    helper = Path(__file__).resolve().with_name("route_reference_regulator.py")
    candidates = [Path("/usr/bin/python3")]
    system_python = shutil.which("python3")
    if system_python:
        candidates.append(Path(system_python))
    python = next(
        (
            str(candidate) for candidate in candidates
            if candidate.is_file()
            and subprocess.run(
                [str(candidate), "-c", "import pcbnew"],
                capture_output=True, text=True, timeout=20, check=False,
            ).returncode == 0
        ),
        None,
    )
    if python is None:
        return {"ok": False, "error": "KiCad pcbnew bindings unavailable for routing"}
    command = [python, str(helper), "--board", str(board)]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=180, check=False
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Reference PCB routing timed out", "command": command}
    return {
        "ok": completed.returncode == 0,
        "mode": "guarded-reference-regulator-routing",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _export_fabrication_package(board: Path, output_dir: Path, cli: str) -> dict[str, object]:
    """Export draft Gerbers and Excellon drills only after the manufacturing gate passes."""
    export_dir = output_dir / "fabrication"
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True)
    commands = [
        [
            cli, "pcb", "export", "gerbers",
            "--layers", "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,Edge.Cuts",
            "-o", str(export_dir), str(board),
        ],
        [cli, "pcb", "export", "drill", "-o", str(export_dir), str(board)],
    ]
    results = []
    for command in commands:
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=180, check=False
            )
            results.append({
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-3000:],
                "stderr": completed.stderr[-3000:],
            })
        except subprocess.TimeoutExpired:
            results.append({
                "command": command,
                "returncode": 124,
                "stdout": "",
                "stderr": "KiCad fabrication export timed out",
            })
    gerber_suffixes = {
        ".gbr", ".gtl", ".gbl", ".gto", ".gbo", ".gts", ".gbs",
        ".gm1", ".gko", ".g1", ".g2",
    }
    gerbers = sorted(
        str(path) for path in export_dir.iterdir()
        if path.is_file() and path.suffix.lower() in gerber_suffixes
    )
    drills = sorted(str(path) for path in export_dir.glob("*.drl"))
    ok = (
        all(item["returncode"] == 0 for item in results)
        and bool(gerbers)
        and bool(drills)
    )
    return {
        "ready": ok,
        "status": "draft-fabrication-package" if ok else "export-failed",
        "directory": str(export_dir),
        "gerber_files": gerbers,
        "drill_files": drills,
        "commands": results,
        "warning": (
            "Draft fabrication outputs only; obtain electrical, thermal, footprint, "
            "and fabrication-house review before ordering boards."
        ),
    }


def _normalize_root_labels(schematics: list[Path]) -> dict[str, object]:
    """Circuit-Synth emits hierarchical labels on the root sheet; make them global.

    Root-sheet hierarchical labels require a parent sheet and produce false ERC
    errors when used in a standalone single-sheet project. Global labels retain
    the named electrical nets without requiring a parent sheet.
    """
    changed: dict[str, int] = {}
    for schematic in schematics:
        source = schematic.read_text(encoding="utf-8")
        updated = source.replace("(hierarchical_label ", "(global_label ")
        count = source.count("(hierarchical_label ")
        if count:
            schematic.write_text(updated, encoding="utf-8")
            changed[str(schematic)] = count
    return {"mode": "root-hierarchical-to-global-label-normalization", "labels_normalized": changed}


def _manufacturing_gate(
    quality: list[dict[str, object]],
    quality_failures: list[str],
    fallback_used: bool,
    routing_succeeded: bool = False,
) -> dict[str, object]:
    """Report manufacturability separately from a successful integration test."""
    unconnected = [
        int(item["unconnected_items"])
        for item in quality
        if item.get("kind") == "DRC"
        and isinstance(item.get("unconnected_items"), int)
        and item["unconnected_items"] != 0
    ]
    blockers = (
        (["PCB fallback remains unrouted"] if fallback_used and not routing_succeeded else [])
        + [f"DRC reports {count} unconnected pads" for count in unconnected]
        + quality_failures
    )
    ready = not blockers and any(item.get("kind") == "DRC" for item in quality)
    return {"passed": ready, "ready": ready, "blocking_reasons": blockers}


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

    summary_path = output_dir / "e2e-summary.json"
    try:
        result = generate_from_source(project_dir, local_source, timeout=600)
    except IntegrationUnavailable as exc:
        result = {"ok": False, "error": str(exc), "source_file": str(local_source)}
    print(json.dumps(result, indent=2, default=str))

    if not result.get("ok", False):
        summary = {
            "generation": result,
            "validation_commands": [],
            "schematics": [],
            "boards": [],
            "note": "Generation failed; ERC/DRC were not run.",
        }
        summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2, default=str))
        print("Circuit-Synth generation failed or produced no KiCad files.", file=sys.stderr)
        return 1

    schematics = sorted(project_dir.rglob("*.kicad_sch"))
    normalization = _normalize_root_labels(schematics)
    boards = sorted(project_dir.rglob("*.kicad_pcb"))
    fallback_result = None
    routing_result = None
    if schematics and not boards:
        board_path = schematics[0].with_suffix(".kicad_pcb")
        fallback_result = _create_pcb_seed(schematics[0], board_path, cli)
        if fallback_result.get("ok"):
            boards = sorted(project_dir.rglob("*.kicad_pcb"))
        else:
            summary = {
                "generation": result,
                "schematic_normalization": normalization,
                "pcb_fallback": fallback_result,
                "validation_commands": [],
                "schematics": [str(path) for path in schematics],
                "boards": [],
                "note": "Schematic exists, but PCB seed generation failed; ERC/DRC were not run.",
            }
            summary_path.write_text(
                json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
            )
            print(json.dumps(summary, indent=2, default=str))
            return 1

    if not schematics or not boards:
        summary = {
            "generation": result,
            "schematic_normalization": normalization,
            "pcb_fallback": fallback_result,
            "validation_commands": [],
            "schematics": [str(path) for path in schematics],
            "boards": [str(path) for path in boards],
            "note": "Expected schematic or PCB missing; ERC/DRC were not run.",
        }
        summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2, default=str))
        print("E2E requires at least one .kicad_sch and one .kicad_pcb.", file=sys.stderr)
        return 1

    if fallback_result and fallback_result.get("ok") and boards:
        routing_result = _route_reference_pcb(boards[0])

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

    quality = []
    for item in reports:
        report_path = Path(str(item["report"]))
        report_text = report_path.read_text(encoding="utf-8", errors="replace") if report_path.is_file() else ""
        if item["kind"] == "ERC":
            match = re.search(r"ERC messages:\s*\d+\s+Errors\s+(\d+)\s+Warnings\s+(\d+)", report_text)
            quality.append({
                "kind": "ERC",
                "errors": int(match.group(1)) if match else None,
                "warnings": int(match.group(2)) if match else None,
                "counts_parsed": match is not None,
                "report": str(report_path),
            })
        else:
            violations = re.search(r"Found\s+(\d+)\s+DRC violations", report_text)
            unconnected = re.search(r"Found\s+(\d+)\s+unconnected pads", report_text)
            quality.append({
                "kind": "DRC",
                "violations": int(violations.group(1)) if violations else None,
                "unconnected_items": int(unconnected.group(1)) if unconnected else None,
                "counts_parsed": violations is not None and unconnected is not None,
                "report": str(report_path),
            })

    fallback_used = bool(fallback_result and fallback_result.get("ok"))
    routing_succeeded = bool(routing_result and routing_result.get("ok"))
    quality_failures = []
    if fallback_used and not routing_succeeded:
        detail = (routing_result or {}).get("error") or (routing_result or {}).get("stderr") or "routing step did not run"
        quality_failures.append(f"Reference PCB routing failed: {detail}")
    for item in quality:
        if not item["counts_parsed"]:
            quality_failures.append(f"Could not parse {item['kind']} report counts")
        elif item["kind"] == "ERC" and item["errors"] != 0:
            quality_failures.append(f"ERC reported {item['errors']} errors")
        elif item["kind"] == "ERC" and item["warnings"] != 0:
            quality_failures.append(f"ERC reported {item['warnings']} warnings")
        elif item["kind"] == "DRC":
            if item["violations"] != 0:
                quality_failures.append(f"DRC reported {item['violations']} violations")
            if item["unconnected_items"] and not (routing_result and routing_result.get("ok")):
                quality_failures.append(
                    f"DRC reported {item['unconnected_items']} unconnected pads"
                )

    manufacturing_gate = _manufacturing_gate(
        quality, quality_failures, fallback_used, routing_succeeded
    )
    fabrication_package = None
    if manufacturing_gate["ready"] and boards:
        fabrication_package = _export_fabrication_package(boards[0], output_dir, cli)

    summary = {
        "generation": result,
        "schematic_normalization": normalization,
        "pcb_fallback": fallback_result,
        "pcb_routing": routing_result,
        "validation_commands": reports,
        "integration_gate": {
            "passed": not quality_failures,
            "checks": [
                "Circuit-Synth generated a KiCad schematic",
                "KiCad generated or validated a PCB file",
                "ERC has zero errors and warnings",
                "DRC has zero geometry violations",
            ],
            "failures": quality_failures,
        },
        "manufacturing_gate": manufacturing_gate,
        "fabrication_package": fabrication_package,
        "quality_gate": {
            "passed": not quality_failures,
            "counts": quality,
            "failures": quality_failures,
            "note": (
                "Unconnected pads are expected only for the explicitly unrouted "
                "PCB placement-seed fallback; they are not acceptable for a routed board."
            ),
        },
        "schematics": [str(path) for path in schematics],
        "boards": [str(path) for path in boards],
        "note": (
            "The fallback is followed by a guarded, reference-design-specific routing "
            "attempt. Automated ERC/DRC success is not a substitute for electrical, "
            "thermal, footprint, and manufacturing review."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))

    if any(item["returncode"] != 0 for item in reports):
        return 1
    if any(not item["report_exists"] for item in reports):
        print("One or more ERC/DRC reports were not created.", file=sys.stderr)
        return 1
    if quality_failures:
        print("ERC/DRC quality gate failed: " + "; ".join(quality_failures), file=sys.stderr)
        return 1
    if manufacturing_gate["ready"] and not (fabrication_package and fabrication_package.get("ready")):
        print("Manufacturing gate passed but Gerber/drill export failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
