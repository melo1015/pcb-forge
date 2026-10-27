#!/usr/bin/env python3
"""CLI entry point for PCB Forge's structural CAM preflight."""
from pcb_forge.integrations.cam_preflight import main

if __name__ == "__main__":
    raise SystemExit(main())
