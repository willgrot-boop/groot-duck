# Electrical reference sheets

These are original vector diagrams derived from the repository configuration,
not photographs or literal PCB pad maps. Both are A3 landscape and available
as high-resolution PNG, editable SVG and printable PDF.

- [03: Logic wiring](03-logic-wiring.png): Pi UART crossing, shared ground,
  I2C connections and separate 3.3 V logic requirements.
- [04: Servo power and channels](04-servo-power-and-channels.png): separate
  positive power path, physical stop, reset-safe control inhibits and all eight
  signal channels.

Wire and verify logic only with the servo V+ supply disconnected. The current
firmware has no motor backend, no runtime hardware arming and no calibrated
servo pulse map. Power wiring in sheet 04 is a future commissioning reference,
not an instruction to energize motors. An electrical drawing does not verify
mounting dimensions, balance, servo torque or component current ratings.

The drawn connection locations are schematic terminal labels. Find the actual
signals on the specific boards you own; do not copy relative pin positions or
assume a servo lead color/header order. Verify breakout supply requirements,
logic voltages and pull-ups. Pull-up/down component values and gate/fuse/stop
ratings must be selected for the actual circuit and measured loads.

Source of truth:

- [`hardware/robot.json`](../../hardware/robot.json)
- [`docs/wiring.md`](../wiring.md)
- [`docs/commissioning.md`](../commissioning.md)

Reproduce with Python and matplotlib from the repository root:

```bash
python scripts/render_build_wiring.py
```

The script reads the eight joint channels directly from `hardware/robot.json`.
Existing CAD assets and previous renders are not changed.
