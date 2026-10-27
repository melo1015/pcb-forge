# CAM/DFM and electrical review — reference regulator_5v

## Scope and evidence

This review is based on the reference source `examples/circuit_synth/regulator_5v.py` and the E2E artifact from run [40550874679](https://github.com/melo1015/pcb-forge/actions/runs/40550874679), commit `51d6830f29a0dba4a141d1ba56df60518ea8b795`.

The artifact contains six Gerber layers (F.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen and Edge.Cuts), one Excellon drill file and a `.gbrjob`. The recorded KiCad export commands returned 0. The package files have KiCad Gerber/Excellon headers and terminators, and the outline Gerber draws a closed rectangular profile. The previous E2E report records ERC 0 errors/0 warnings and DRC 0 violations/0 unconnected pads.

**This is a preflight, not a fabrication release.** No independent CAM viewer or fabrication-house CAM system has been run in this environment. The structural checker added in `scripts/validate_fabrication_package.py` checks file presence and syntax markers, not image geometry, copper connectivity, clearances, annular rings, mask slivers or manufacturer-specific rules.

## CAM / DFM findings

### Passes observed

- Required two-layer copper, top/bottom solder mask, top silkscreen and board-profile Gerbers are present.
- The Excellon file contains a tool table and coordinates, and is terminated with `M30`.
- The Gerber job file identifies a two-copper-layer stack and reports nominal board dimensions of approximately **135.1 × 80.1 mm**, 1.6 mm thickness and 35 µm copper.
- The profile Gerber contains a closed rectangular path approximately 135 × 80 mm.
- KiCad export commands completed successfully in the recorded run.

### Issues / decisions before ordering

1. **Board area is unusually large for this five-component reference circuit.** The outline is about 10,800 mm². This is not inherently invalid, but appears to reflect the generic placement seed rather than a compact product layout. Re-place the parts to suit the enclosure, connector access, thermal spreading and short regulator-capacitor loops; then rerun DRC and regenerate all outputs.
2. **Confirm the fabrication quote/rules.** The job metadata reports a 0.2 mm minimum pad-to-pad, pad-to-track and track-to-track spacing and a 0.4 mm minimum line width. Ask the chosen fab to confirm these are acceptable for the selected process and that the intended copper weight, finished board thickness, finish and tolerances are supported. The job file says finish `None`; specify the required finish (for example, HASL or ENIG) in the order rather than assuming it.
3. **Check the drill interpretation.** The drill file has three tool diameters (0.8, 1.0 and 1.1 mm) and 11 coordinates. Verify plated-through-hole intent, finished hole diameters, annular rings, connector pin fit and tool-to-copper clearance in the fabricator's CAM viewer.
4. **Silkscreen and mask visual review remains outstanding.** Inspect reference/value text against pads and board edge; confirm no text is clipped, no exposed copper is unintentionally masked, and no narrow mask slivers violate the fab's minimum.
5. **No bottom silkscreen or solder-paste Gerber is exported.** This can be appropriate for an all-through-hole board with top-only legends, but confirm it matches the assembly process. If the assembler needs paste, assembly drawings or a bottom legend, export those layers deliberately.
6. **Review the job file as a production specification.** Revision is `rev?` and finish is `None`; replace placeholders and make stack-up, copper weight, finish and dimensions explicit for the actual order.

## Electrical review

### Connectivity supported by the source and E2E report

The reference circuit is a linear 5 V regulator based on `Regulator_Linear:L7805`, in a TO-220-3 vertical footprint. It assigns U1 pin 1 to VIN, pin 2 to GND and pin 3 to VOUT_5V. C1 is 330 nF from VIN to GND, C2 is 100 nF from VOUT_5V to GND, and two-pin connectors expose input and output. These values are consistent with common bypass-capacitor values for a classic 7805-style linear regulator, but the exact manufacturer's datasheet and variant must govern final selection.

ERC/DRC success supports the tool's connectivity and geometric checks; it does not verify component ratings, current capacity, thermal safety, transient behavior or connector suitability.

### Blocking electrical questions

- **Input range is unspecified.** Do not connect an arbitrary DC source. The exact L7805 variant's maximum input voltage, minimum operating headroom and transient limits must be checked against the real source.
- **Load current is unspecified.** A linear regulator dissipates approximately `(VIN − 5 V) × ILOAD`, plus quiescent effects. Illustrative values (not an approved operating envelope):
  - 9 V input at 100 mA: about 0.4 W.
  - 12 V input at 100 mA: about 0.7 W.
  - 12 V input at 500 mA: about 3.5 W.
  - 24 V input at 100 mA: about 1.9 W.
  These losses can overheat a TO-220 regulator without suitable copper/heatsinking and ambient-temperature margin. The 12 V / 500 mA example is a strong thermal warning, not a claim that the board can support it.
- **Capacitor ratings and technologies are absent.** The schematic values do not specify voltage rating, tolerance, dielectric, polarity or temperature rating. Select parts from the chosen regulator datasheet and input-transient environment; do not infer these properties from the values alone.
- **Protection is not shown.** Decide whether the application requires input fuse/current limiting, reverse-polarity protection, input transient suppression, output short-circuit handling or a protection diode from output to input. Requirements depend on the source, load and wiring.
- **Power connectors are generic 2.54 mm pin headers.** Confirm their rated current, contact resistance, wire termination, mechanical retention and temperature rise. They may be inappropriate for a power product or high current.
- **Trace sizing is not proven by DRC.** The routing fixture uses 0.4 mm VOUT and 0.5 mm VIN/GND tracks. Current, copper thickness, permitted temperature rise, ambient temperature, path length and return-current geometry must be known before those widths can be approved.
- **The layout is a test fixture, not an optimized power layout.** Keep the input/output capacitors close to the regulator's relevant pins, minimize high-current loop area, ensure ground return continuity, and provide a thermal path compatible with the chosen load.

## Release gate

Do **not** mark this design production-ready until all are complete:

- [ ] Define input minimum/nominal/maximum, load-current range, ambient temperature and expected duty cycle.
- [ ] Select an exact regulator MPN and verify its datasheet pinout, operating limits, capacitor requirements, thermal resistance and protection guidance.
- [ ] Select exact capacitor MPNs with voltage/temperature/tolerance ratings.
- [ ] Verify connector and trace current ratings and calculate worst-case regulator junction temperature with the actual PCB copper/heatsink.
- [ ] Review the board in KiCad's 3D viewer and an independent Gerber/CAM viewer; inspect outline, copper, masks, silkscreen and drill registration.
- [ ] Run the new structural package check and KiCad ERC/DRC after every layout change.
- [ ] Have the selected fabricator confirm the job's dimensions, stack-up, finish, clearances, drill plating and file set.
- [ ] Build and electrically test a prototype under current limit: verify output at min/max input and min/max load, startup, load transient, thermal steady state, reverse connection/transient cases where applicable.

## Run the structural package check

After extracting the E2E artifact so that the Gerbers, `.drl` and `.gbrjob` are in one directory:

```bash
python scripts/validate_fabrication_package.py path/to/fabrication \
  --json-out path/to/cam-preflight.json
```

A `PASS_STRUCTURAL_PREFLIGHT` means only that required files and basic format markers passed. It is not a CAM/DFM sign-off and must not bypass the release gate above.
