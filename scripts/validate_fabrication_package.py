#!/usr/bin/env python3
"""Independent structural checks for a KiCad Gerber/Excellon fabrication package.

This is a lightweight CAM preflight, not a CAM viewer, DFM certification, or
replacement for KiCad DRC / the fabricator's CAM inspection.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_LAYERS = {
    "F.Cu": (".gtl", ".gbr"),
    "B.Cu": (".gbl",),
    "F.Mask": (".gts",),
    "B.Mask": (".gbs",),
    "F.Silkscreen": (".gto",),
    "Edge.Cuts": (".gm1", ".gko",),
}


def _find_layer(files: list[Path], suffixes: tuple[str, ...], layer: str) -> Path | None:
    matches = [
        path for path in files
        if path.suffix.lower() in suffixes
        and (layer.replace(".", "_").lower() in path.stem.lower()
             or (layer == "F.Cu" and path.suffix.lower() == ".gtl")
             or (layer == "B.Cu" and path.suffix.lower() == ".gbl")
             or (layer == "F.Mask" and path.suffix.lower() == ".gts")
             or (layer == "B.Mask" and path.suffix.lower() == ".gbs")
             or (layer == "F.Silkscreen" and path.suffix.lower() == ".gto")
             or (layer == "Edge.Cuts" and path.suffix.lower() in {".gm1", ".gko"}))
    ]
    return matches[0] if matches else None


def _check_gerber(path: Path, layer: str) -> list[str]:
    issues: list[str] = []
    data = path.read_text(encoding="ascii", errors="replace")
    if not data.strip():
        return [f"{layer}: file is empty"]
    if "%MOMM*%" not in data and "%MOIN*%" not in data:
        issues.append(f"{layer}: missing explicit Gerber unit declaration")
    if "%FSL" not in data:
        issues.append(f"{layer}: missing coordinate format declaration")
    if "M02*" not in data:
        issues.append(f"{layer}: missing Gerber end-of-file command M02*")
    if not re.search(r"D0?1\*", data):
        issues.append(f"{layer}: no draw operations (D01*) found")
    if not re.search(r"%ADD\d+", data):
        issues.append(f"{layer}: no aperture definitions found")
    if layer == "Edge.Cuts":
        coords = re.findall(r"X(-?\d+)Y(-?\d+)D0([12])\*", data)
        path_coords = [(x, y) for x, y, _op in coords]
        draw_count = sum(1 for _x, _y, op in coords if op == "1")
        if draw_count < 4:
            issues.append("Edge.Cuts: fewer than four draw coordinates; outline may be incomplete")
        elif path_coords[-1] != path_coords[0]:
            issues.append("Edge.Cuts: final draw coordinate does not close to the first draw coordinate")
    return issues


def validate_package(package_dir: Path) -> dict[str, Any]:
    """Check required Gerber layers, drill file, and optional Gerber job JSON."""
    if not package_dir.is_dir():
        return {
            "passed": False,
            "status": "FAIL",
            "package_dir": str(package_dir),
            "checks": [],
            "blocking_issues": [f"Package directory does not exist: {package_dir}"],
            "warnings": [],
        }

    files = [p for p in package_dir.iterdir() if p.is_file()]
    checks: list[dict[str, Any]] = []
    blocking: list[str] = []
    warnings: list[str] = []

    for layer, suffixes in REQUIRED_LAYERS.items():
        path = _find_layer(files, suffixes, layer)
        if path is None:
            blocking.append(f"Missing required Gerber layer: {layer}")
            checks.append({"check": f"layer:{layer}", "passed": False, "file": None})
            continue
        issues = _check_gerber(path, layer)
        blocking.extend(issues)
        checks.append({
            "check": f"layer:{layer}",
            "passed": not issues,
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "issues": issues,
        })

    drills = sorted(p for p in files if p.suffix.lower() == ".drl")
    if not drills:
        blocking.append("Missing Excellon drill file (*.drl)")
        checks.append({"check": "excellon", "passed": False, "file": None})
    else:
        drill = drills[0]
        data = drill.read_text(encoding="ascii", errors="replace")
        drill_issues: list[str] = []
        if not data.lstrip().startswith("M48"):
            drill_issues.append("Excellon header M48 is missing")
        if not re.search(r"(?m)^M30\s*$", data):
            drill_issues.append("Excellon end command M30 is missing")
        tools = re.findall(r"(?m)^T\d+C\d+(?:\.\d+)?\s*$", data)
        coordinates = re.findall(r"(?m)^X-?\d+(?:\.\d+)?Y-?\d+(?:\.\d+)?\s*$", data)
        if not tools:
            drill_issues.append("No drill tool definitions found")
        if not coordinates:
            drill_issues.append("No drill coordinates found")
        if not re.search(r"(?m)^(?:METRIC|INCH)\s*$", data):
            drill_issues.append("No explicit METRIC/INCH unit declaration found")
        blocking.extend(drill_issues)
        checks.append({
            "check": "excellon",
            "passed": not drill_issues,
            "file": drill.name,
            "size_bytes": drill.stat().st_size,
            "tool_definitions": len(tools),
            "drill_coordinates": len(coordinates),
            "issues": drill_issues,
        })

    job_files = [p for p in files if p.name.lower().endswith(".gbrjob")]
    if job_files:
        try:
            job = json.loads(job_files[0].read_text(encoding="utf-8"))
            attrs = job.get("FilesAttributes", [])
            functions = {str(item.get("FileFunction", "")) for item in attrs}
            required_functions = {
                "Copper,L1,Top", "Copper,L2,Bot", "SolderMask,Top",
                "SolderMask,Bot", "Legend,Top", "Profile",
            }
            missing_functions = sorted(required_functions - functions)
            job_issues = [f"Gerber job metadata missing layer function: {item}" for item in missing_functions]
            blocking.extend(job_issues)
            checks.append({
                "check": "gerber-job",
                "passed": not job_issues,
                "file": job_files[0].name,
                "layer_functions": sorted(functions),
                "issues": job_issues,
            })
        except (json.JSONDecodeError, OSError) as exc:
            blocking.append(f"Invalid Gerber job JSON: {exc}")
            checks.append({"check": "gerber-job", "passed": False, "file": job_files[0].name})

    if len(drills) > 1:
        warnings.append(
            f"Found {len(drills)} drill files; confirm which files are plated/non-plated "
            "and which one the fabricator expects."
        )
    if not job_files:
        warnings.append("No .gbrjob metadata file found; confirm layer mapping manually.")

    return {
        "passed": not blocking,
        "status": "PASS_STRUCTURAL_PREFLIGHT" if not blocking else "FAIL",
        "package_dir": str(package_dir),
        "files_seen": sorted(p.name for p in files),
        "checks": checks,
        "blocking_issues": blocking,
        "warnings": warnings,
        "scope_note": (
            "Structural checks only. Does not establish electrical correctness, "
            "clearance/annular-ring adequacy, solder-mask slivers, silkscreen clipping, "
            "plating intent, impedance, thermal safety, or compliance with a specific fab."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path, help="Directory containing exported Gerbers and Excellon")
    parser.add_argument("--json-out", type=Path, help="Optional path to write the JSON report")
    args = parser.parse_args()
    report = validate_package(args.package_dir.resolve())
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
