"""Create an unrouted KiCad PCB placement seed from a generated schematic netlist.

Fallback for Circuit-Synth distributions that generate schematics but omit the
licensed PCB-generation integration. This does NOT route tracks or certify a
manufacturable design.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew


def _point(x_mm: float, y_mm: float):
    """Support KiCad 7's wxPoint and newer vector-based bindings."""
    if hasattr(pcbnew, "VECTOR2I"):
        return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))
    return pcbnew.wxPoint(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schematic", required=True, type=Path)
    parser.add_argument("--board", required=True, type=Path)
    parser.add_argument("--kicad-cli", required=True)
    args = parser.parse_args()

    schematic = args.schematic.resolve()
    board_path = args.board.resolve()
    if not schematic.is_file():
        raise FileNotFoundError(schematic)

    with tempfile.TemporaryDirectory(prefix="pcb-forge-netlist-") as tmp:
        netlist_path = Path(tmp) / "design.net"
        proc = subprocess.run(
            [args.kicad_cli, "sch", "export", "netlist", "--format", "kicadxml",
             "-o", str(netlist_path), str(schematic)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        if proc.returncode != 0 or not netlist_path.is_file():
            raise RuntimeError(
                f"KiCad netlist export failed ({proc.returncode}): "
                f"{proc.stderr[-3000:]} {proc.stdout[-3000:]}"
            )
        root = ET.parse(netlist_path).getroot()

    components: dict[str, dict[str, str]] = {}
    for component in root.findall(".//components/comp"):
        ref = component.get("ref", "")
        footprint = (component.findtext("footprint") or "").strip()
        value = (component.findtext("value") or ref).strip()
        if ref and footprint:
            components[ref] = {"footprint": footprint, "value": value}
    if not components:
        raise RuntimeError("Netlist contains no components with assigned footprints")

    board = pcbnew.BOARD()
    net_items: dict[str, object] = {}
    for code, net in enumerate(root.findall(".//nets/net"), start=1):
        name = net.get("name", "")
        if not name:
            continue
        item = pcbnew.NETINFO_ITEM(board, name, code)
        board.Add(item)
        net_items[name] = item

    footprint_root = Path("/usr/share/kicad/footprints")
    placed: dict[str, object] = {}
    x, y = 35.0, 35.0
    for ref, info in sorted(components.items()):
        if ":" not in info["footprint"]:
            raise RuntimeError(f"Invalid footprint identifier for {ref}: {info['footprint']}")
        library, footprint_name = info["footprint"].split(":", 1)
        library_path = footprint_root / f"{library}.pretty"
        footprint = pcbnew.FootprintLoad(str(library_path), footprint_name)
        if footprint is None:
            raise RuntimeError(f"Could not load footprint {info['footprint']} for {ref}")
        footprint.SetReference(ref)
        footprint.SetValue(info["value"])
        footprint.SetPosition(_point(x, y))
        board.Add(footprint)
        placed[ref] = footprint
        x += 25.0
        if x > 130.0:
            x, y = 35.0, y + 30.0

    for net in root.findall(".//nets/net"):
        net_item = net_items.get(net.get("name", ""))
        if net_item is None:
            continue
        for node in net.findall("node"):
            footprint = placed.get(node.get("ref", ""))
            if footprint is None:
                continue
            for pad in footprint.Pads():
                if pad.GetNumber() == node.get("pin", ""):
                    pad.SetNet(net_item)

    outline = pcbnew.PCB_SHAPE()
    outline.SetShape(pcbnew.SHAPE_T_RECT)
    outline.SetStart(_point(20, 20))
    outline.SetEnd(_point(155, 100))
    outline.SetLayer(pcbnew.Edge_Cuts)
    board.Add(outline)

    board_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(board_path), board)
    if not board_path.is_file() or board_path.stat().st_size == 0:
        raise RuntimeError("KiCad PCB file was not written")
    print(
        f"Created unrouted PCB placement seed: {board_path} "
        f"({len(placed)} footprints, {len(net_items)} nets)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
