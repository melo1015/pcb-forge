"""Route the fixed PCB Forge 5 V reference board after the netlist fallback.

This is deliberately design-specific. It validates expected references, pad
numbers, and net names before adding tracks. It is an integration fixture, not
a substitute for electrical/thermal engineering or manufacturing review.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def _point(x_mm: float, y_mm: float):
    if hasattr(pcbnew, "VECTOR2I"):
        return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))
    return pcbnew.wxPoint(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def _mm(point) -> tuple[float, float]:
    return pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)


def _pads(board) -> dict[tuple[str, str], object]:
    found = {}
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        for pad in footprint.Pads():
            found[(ref, pad.GetNumber())] = pad
    return found


def route_board(board_path: Path) -> dict[str, object]:
    board = pcbnew.LoadBoard(str(board_path))
    if board is None:
        raise RuntimeError(f"KiCad could not load board: {board_path}")
    pads = _pads(board)

    expected = {
        ("C1", "1"): "VIN", ("U1", "1"): "VIN", ("J1", "1"): "VIN",
        ("C1", "2"): "GND", ("C2", "2"): "GND", ("U1", "2"): "GND",
        ("J1", "2"): "GND", ("J2", "2"): "GND",
        ("U1", "3"): "VOUT_5V", ("C2", "1"): "VOUT_5V", ("J2", "1"): "VOUT_5V",
    }
    for key, net_name in expected.items():
        pad = pads.get(key)
        if pad is None:
            raise RuntimeError(f"Expected reference-design pad missing: {key[0]}.{key[1]}")
        if pad.GetNetname() != net_name:
            raise RuntimeError(
                f"Net mapping mismatch at {key[0]}.{key[1]}: "
                f"expected {net_name}, got {pad.GetNetname()!r}"
            )

    # Routes are explicit waypoints in millimetres, chosen for this exact
    # placement seed. VIN/VOUT use F.Cu; GND uses B.Cu to avoid cross-net
    # intersections. Through-hole pads provide layer transitions.
    routes = [
        ("VIN", pcbnew.F_Cu, 0.50, [
            [("C1", "1"), (25, 35), (25, 25), (85, 25), ("J1", "1")],
            [("U1", "1"), (25, 65)],
            [(25, 65), (25, 35)],
        ]),
        ("VOUT_5V", pcbnew.F_Cu, 0.40, [
            [("U1", "3"), (50, 65), (50, 50), (55, 50), (55, 35), ("C2", "1")],
            [("C2", "1"), (55, 35), (55, 30), (110, 30), ("J2", "1")],
        ]),
        ("GND", pcbnew.B_Cu, 0.50, [
            [("U1", "2"), (37.54, 75), (50, 75), (50, 30), (65, 30), ("C2", "2")],
            [("C1", "2"), (40, 30), (50, 30)],
            [("C2", "2"), (70, 45), (85, 45), ("J1", "2")],
            [("J1", "2"), (95, 45), (110, 45), ("J2", "2")],
        ]),
    ]

    # Do not silently duplicate tracks if the script is re-run on an already
    # routed board. This script expects the freshly generated fallback seed.
    if any(True for _ in board.GetTracks()):
        raise RuntimeError("Board already contains tracks; refusing to route twice")

    added = 0
    for net_name, layer, width_mm, paths in routes:
        for path in paths:
            resolved = []
            for node in path:
                if isinstance(node[0], str):
                    pad = pads[(node[0], node[1])]
                    if pad.GetNetname() != net_name:
                        raise RuntimeError(f"Route {net_name} touches wrong-net pad {node[0]}.{node[1]}")
                    resolved.append(pad.GetPosition())
                else:
                    resolved.append(_point(float(node[0]), float(node[1])))
            for start, end in zip(resolved, resolved[1:]):
                if _mm(start) == _mm(end):
                    continue
                track = pcbnew.PCB_TRACK(board)
                track.SetStart(start)
                track.SetEnd(end)
                track.SetWidth(pcbnew.FromMM(width_mm))
                track.SetLayer(layer)
                track.SetNetCode(pads[next(k for k, p in pads.items() if p.GetNetname() == net_name)].GetNetCode())
                board.Add(track)
                added += 1

    pcbnew.SaveBoard(str(board_path), board)
    reloaded = pcbnew.LoadBoard(str(board_path))
    if reloaded is None:
        raise RuntimeError("KiCad could not reload routed board after save")
    track_count = sum(1 for _ in reloaded.GetTracks())
    if track_count != added:
        raise RuntimeError(f"Track count mismatch after save: expected {added}, got {track_count}")
    return {"ok": True, "board": str(board_path), "tracks_added": added, "tracks_after_reload": track_count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", required=True, type=Path)
    args = parser.parse_args()
    result = route_board(args.board.resolve())
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
