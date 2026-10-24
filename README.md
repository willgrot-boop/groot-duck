# DIY Microduck-inspired biped prototype

A simulation-first **eight-servo** robot scaffold with a target **$200 hardware
budget**. Raspberry Pi Zero 2 W is the planned camera, voice, Wi-Fi and optional
cloud-AI host. An ESP32 owns local motion safeguards and IMU feedback.

**This robot has not demonstrated balance or walking.** The Python demo only
interpolates joint angles. The ESP32 firmware deliberately has no motor-output
backend: it boots with servo power inhibited and PCA9685 PWM outputs disabled;
UART cannot arm it. No servos were connected, calibrated, flashed or actuated
during this work.

## Quick start: no hardware or credentials

Requires Python 3.10+; run from the repository root. The host package has no
third-party runtime dependencies. Existing CAD tools are optional and separate.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m microduck check-config
.venv/bin/python -m microduck simulate --duration 1
.venv/bin/python -m unittest discover -s tests -v
bash firmware/test_native.sh
```

The last command requires a C++17 `g++` compiler. On Windows, activate the venv
and use `python` in place of `.venv/bin/python`; use WSL for the native shell test.

Simulation emits JSON lines with `simulated: true` and `imu_valid: false`.
`state: "armed"` in these records refers only to the software simulator. Time is
virtual by default; `--realtime` paces the demo on the host clock. The small head
scan is a software demonstration, not a gait or a physics simulation. Config
paths are relative to the working directory; use `--config /path/to/robot.json`
before the subcommand when running elsewhere.

```bash
.venv/bin/python -m microduck protocol-status
```

This prints a protocol status request. It does not open a serial port. There is
no real-motor transport or hardware-arm CLI. Missing hardware and network access
do not prevent host tests or joint simulation.

## Repository layout

| Path | Purpose |
|---|---|
| `src/microduck/` | Validated configuration, bounded motion interface, simulated backend, protocol codec and Pi service boundaries |
| `firmware/` | ESP32 UART and raw MPU6050 sampling, portable safety core and native tests; motor outputs inhibited |
| `hardware/robot.json` | Eight-joint map, example simulation limits, pin assignments and power assumptions |
| `hardware/calibration.example.json` | Uncalibrated template: false approvals and null measurements |
| `hardware/bom.csv` | Itemized $200 bench-prototype estimate |
| `tests/` | Host safety, motion, protocol, configuration, budget and CLI tests |
| `docs/` | Architecture, wiring, commissioning gates, roadmap and prior CAD documentation |
| `cad/`, `exports/`, `reference/` | Preserved visual CAD, exports and attributed official mesh references |
| `.github/workflows/prototype.yml` | Python, native safety/protocol tests and ESP32 build jobs on push/PR |

## Hardware design and budget

| PCA9685 channel | Joint |
|---|---|
| 0 / 3 | Left / right hip pitch |
| 1 / 4 | Left / right knee |
| 2 / 5 | Left / right ankle pitch |
| 6 / 7 | Head pan / tilt |

This gives three pitch joints per leg and two head joints. It has no hip-roll
or ankle-roll joints, so lateral balance authority is limited. Eight servos
are a starting design, not evidence that a free-standing biped is feasible.

The [BOM](hardware/bom.csv) totals **$200**, including eight candidate MG90S-class
servos, Pi/camera/audio, ESP32, IMU, PWM board, separate logic and servo supplies,
power gate, wiring/fuses, a physical stop, printing and a $5 contingency.
Prices are planning estimates, not quotes. Tax, shipping, tools, battery power
and cloud-service charges are excluded. Servo quality, torque, continuous-load
capability and actual stall current must be checked before purchase/assembly;
a smaller/lighter mechanism or a revised budget may be necessary.

The existing ~274 mm CAD model is a **visual reference** and has not been
regenerated or adapted to eight low-cost servos. Do not print it expecting
working mounts, link lengths, suitable mass or calibrated joints.
See [the CAD documentation](docs/cad-model.md) and [hardware notes](hardware/README.md).

For illustrated component placement, mechanical dry-fit steps and exact
wiring diagrams, open the [four-sheet build guide](docs/build-guide/README.md)
or [printable PDF](docs/build-guide/microduck-build-guide.pdf). Its mechanical
illustrations are proposed layouts, not verified eight-servo mounting plans.

## Control boundaries

- **Pi:** future camera, microphone/speech, speaker and cloud adapters. The
  package currently defines interfaces and a small action allowlist; those
  integrations are not implemented or hardware-tested. Cloud proposals cannot
  arm firmware or send arbitrary servo pulses. No API keys are required now.
- **ESP32:** JSON-lines UART at 115200 baud; bounded parsing, command validation,
  latched faults/stops, 500 ms watchdog core, and raw MPU6050 acceleration/gyro
  feedback. No balance estimation/controller is included. Real sampling code
  exists, but physical sensor operation is unverified.
- **Power:** Pi and ESP32 logic use a separate regulated rail from the servos.
  Grounds are shared; never draw servo current through the Pi. External OE
  pullup and power-gate pulldown keep motors off during reset. A physical
  latching stop cuts servo power independently of software.

Firmware build and protocol instructions are in [firmware/README.md](firmware/README.md).
Build only—do not flash or wire powered servos as part of the quick start.
Physical calibration, measured limits, current/power checks, mechanical support
and an independently proven stop are prerequisites for a future motor backend.
Changing a JSON flag does not enable motors.

Local Python and native firmware checks passed. The ESP32 target build was
attempted but its PlatformIO dependency downloads were blocked by the cloud
network proxy (HTTP 403); that build and all physical hardware remain
unverified. See [validation notes](docs/validation.md) for exact scope and the
command to retry once registry access is available. Defined CI jobs are not
evidence that a remote CI run has passed.

## Next development steps

1. Prove torque, mass and mounting feasibility with actual servo samples.
2. Validate UART, IMU and electrical stop behavior on a logic-only bench.
3. Implement and test a commissioned output backend with measured calibration
   and local authorization; then test one unloaded joint under supervision.
4. Assemble a supported robot and verify fault/current/thermal behavior.
5. Add measured Pi camera/audio/cloud integrations; investigate balance only
   after a suitable mechanical and contact model exists.

See the acceptance criteria in the [roadmap](docs/roadmap.md),
[architecture](docs/architecture.md), [wiring](docs/wiring.md), and
[commissioning checklist](docs/commissioning.md).

The CAD archives remain the original CAD deliverables, not archives of this
new software scaffold. Model attribution and CC BY-NC-SA 4.0 terms remain in
[LICENSE-MODEL.md](LICENSE-MODEL.md) and `reference/`.
