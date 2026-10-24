# Proposed wiring

This pinout targets a **classic ESP32-WROOM DevKit / `esp32dev`**. It is not a
pinout for ESP32-C3, S2 or S3 boards. Verify your actual board's labels,
regulators, boot behavior and USB power path before connecting supplies.

Keep the servo V+ supply disconnected during logic bring-up and serial tests.
No motor should be connected during initial firmware or I2C verification.

## Logic and communication

| Signal | Raspberry Pi Zero 2 W | ESP32 / device |
|---|---|---|
| UART Pi → ESP32 | GPIO14 TXD, physical pin 8 | GPIO16 RX2 |
| UART ESP32 → Pi | GPIO15 RXD, physical pin 10 | GPIO17 TX2 |
| Signal ground | Pi ground, e.g. physical pin 6 | ESP32 ground and device ground |
| I2C SDA | No Pi connection | GPIO21 → MPU6050 SDA and PCA9685 SDA |
| I2C SCL | No Pi connection | GPIO22 → MPU6050 SCL and PCA9685 SCL |
| Servo gate command | No Pi connection | GPIO26 → 3.3 V compatible active-high power gate; external pull-down |
| PCA9685 output disable | No Pi connection | GPIO25 → OE; external pull-up to 3.3 V |

Use 115200 baud, 8 data bits, no parity, 1 stop bit and 3.3 V levels. Cross TX
to RX, not TX to TX. Configure the Pi's UART and disable its serial login console
before connecting an ESP32; OS console messages are not robot commands. Check
the Pi documentation for stable `/dev/serial0` mapping on the chosen OS.

The MPU6050 address is `0x68` with AD0 low. PCA9685 uses `0x40` with address
straps in their default low state. Check for address conflicts and actual
pull-up voltages with a meter. Feed PCA9685 **logic VCC from 3.3 V**, and keep
all I2C pull-ups at 3.3 V. Breakout-board supply regulators do not necessarily
make their signal pins 5 V tolerant.

## Separate power paths

```text
5 V logic supply ── fused/appropriate USB paths ── Pi + ESP32 logic

5 V high-current servo supply
    └── fuse ── latching physical disconnect ── default-off power gate
          └── PCA9685 servo V+ ── eight servo V+ wires

All signal grounds join at a suitable common ground distribution point.
Servo return current uses heavy short wiring, not Pi traces or a breadboard.
```

The 5 V rails are separate positive supplies. Do not connect their positive
outputs together or backfeed Pi USB, ESP32 USB or board 5 V regulator paths.
Follow the particular board's power-input rules when USB and bench supplies
are present. Never feed 5 V into a GPIO or the Pi 3.3 V rail.

PCA9685 servo V+ is different from its logic VCC. A board's servo-header positive
rail is not a Pi power output. The servo supply candidate is 5 V at 8–10 A;
this is a budget allowance, **not a measured current requirement**. Measure
the selected servos' loaded peaks/stall conditions safely with one unit first,
then size the supply, fuse, gate, stop contacts, wiring and connectors for the
actual concurrent load. Do not deliberately hold a servo stalled to collect data.

GPIO26 only controls a properly rated high-side gate or load-switch circuit.
It must never carry motor current or directly switch eight servo power wires.
Use an external pull-down so the gate is off during reset, flashing and while
the ESP32 is unplugged. A generic relay module that powers up active is not an
acceptable substitute without verifying its whole startup behavior.

PCA9685 OE is active **high = outputs disabled**. Add a 3.3 V pull-up so reset
or disconnected GPIO25 leaves it disabled. Some breakout boards pull OE low;
inspect and modify the actual board as required instead of assuming the pin
defaults safe. OE is an additional inhibit, not the independent power cutoff:
some servo types behave differently when their PWM signal disappears.

The latching physical stop must cut the servo power path without relying on
the ESP32, Pi, I2C, GPIO, USB cable or cloud connection. Use components rated
for the measured DC current. Verify that it opens the rail and stays latched.
The firmware's `estop` message supplements this hardware device; it cannot
replace it.

## Before motors

With servo V+ disconnected, verify polarity, ground, signal voltage, no
backfeeding and the firmware's default disabled status. Confirm gate off/OE high
during reset and flashing. Apply the physical stop and prove power removal
using a meter or appropriate dummy load. Calibrate one unloaded servo in a
fixture only after the future commissioning software is implemented and the
[commissioning gates](commissioning.md) are met.
