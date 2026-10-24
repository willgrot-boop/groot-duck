# ESP32 motion/IMU scaffold

This target is for a **classic ESP32 DevKit (`esp32dev`)**, not an ESP32-C3/S3.
It implements UART framing, eight-joint command validation, disarm/emergency-stop
state handling, and real MPU6050 sensor acquisition. **The motor backend is
deliberately absent. No command enables PWM or motor power.** This is not a
balance controller, walking firmware, or a ready-to-run motor controller.

## Wiring contract

| ESP32 signal | GPIO | Connection |
| --- | ---: | --- |
| UART2 RX | 16 | Pi GPIO14/TX, 3.3 V logic |
| UART2 TX | 17 | Pi GPIO15/RX, 3.3 V logic |
| I2C SDA/SCL | 21 / 22 | MPU6050 `0x68`; future PCA9685 `0x40`, logic at 3.3 V |
| Motor-power enable | 26 | External active-high power gate; external pulldown required |
| PCA9685 OE | 25 | Active-low OE; external pullup to **3.3 V** required |

Share logic ground. The GPIO cannot supply servo power. Use a separate rated
servo rail and a physical power disconnect/emergency stop; the gate and OE
lines alone are not a physical emergency stop. The external pulldown/pullup
must keep power disabled during reset and before `setup()` executes. This
scaffold does not read an emergency-stop input or monitor supply voltage/current,
and reports that physical authorization has not been verified.

At boot and every loop, GPIO26 is low and GPIO25 is high. The PCA9685 is never
initialized or written. Calibration validity, bench approval, physical e-stop
clear and backend readiness remain false. UART `arm` always fails with
`motor_backend_disabled`; providing authorization/calibration fields in JSON
does not bypass this restriction. Safe commissioning and a hardware backend
must be implemented and tested in a later milestone before any motor output.

## Joint contract

Angles are logical model degrees, not raw servo shaft angles or pulse widths.
Mirrored geometry still needs individual measured servo direction and offset.

| Channel | Joint | Provisional allowed degrees | Simulation neutral |
| ---: | --- | --- | ---: |
| 0 | `left_hip_pitch` | -35 .. 35 | 0 |
| 1 | `left_knee` | 0 .. 75 | 20 |
| 2 | `left_ankle_pitch` | -30 .. 30 | 0 |
| 3 | `right_hip_pitch` | -35 .. 35 | 0 |
| 4 | `right_knee` | 0 .. 75 | 20 |
| 5 | `right_ankle_pitch` | -30 .. 30 | 0 |
| 6 | `head_pan` | -60 .. 60 | 0 |
| 7 | `head_tilt` | -25 .. 25 | 0 |

These examples are software envelopes, not calibrated or mechanically tested
limits. Maximum target velocity is 60 deg/s. `include/motion_safety.hpp` is a
portable policy core: complete frames are validated before any joint changes;
invalid targets do not refresh its 500 ms command watchdog. Watchdog expiry or
loss of a required safety input latches `fault`. Emergency stop latches `estop`.
Neither state can be cleared with `disarm` or `arm`; a restart returns to
disarmed, never to automatic motion. The core is tested with simulated trusted
prerequisites, but production firmware never supplies those prerequisites.

## UART protocol v1

UART2 is 115200 baud, 8N1. Requests are UTF-8/ASCII JSON objects terminated by a
newline, maximum **512 bytes before the newline**. Oversized lines are discarded
through the next newline. Unparseable requests receive `seq: 0`; valid requests
require an integer `seq` in 0..2147483647, integer `v: 1`, and string `type`.
Unexpected fields, duplicate object keys (including escaped duplicate keys),
and trailing content after the object are rejected. Only `target` accepts the
additional `positions_deg` member.

```json
{"v":1,"seq":1,"type":"status"}
{"v":1,"seq":2,"type":"disarm"}
{"v":1,"seq":3,"type":"estop"}
```

Response shape (additional telemetry accompanies status):

```json
{"v":1,"seq":1,"type":"status","state":"disarmed","outputs_enabled":false,"firmware_mode":"no_motor_backend","calibration_valid":false,"physical_estop_verified":false,"imu":{"valid":false,"sample_ms":0,"calibrated":false,"filtered":false}}
```

`arm` is a defined but always-rejected command in this scaffold. `target` requires
`positions_deg` containing **all eight exact joint names** and finite numeric
values. Valid target frames are still rejected as `not_armed`; targets are never
queued for later motion. Unknown commands and malformed frames return `error`.
Status queries do not refresh the motion watchdog.

The MPU6050 is identified using WHO_AM_I, woken and explicitly configured for
±2 g and ±250 deg/s. Samples are attempted every 20 ms. Status returns
`imu.valid`, `sample_ms`, `calibrated: false` and `filtered: false`; fresh samples
also include `accel_g` and `gyro_dps` arrays. These are scaled sensor readings,
not calibrated attitude or an indication of balance. Failed or older-than-100-ms
samples are invalid and omit the reading arrays. Missing IMU hardware is a
normal invalid-telemetry condition; it never enables motion.

## Build and tests

Native policy tests require only `g++` with C++17:

```bash
sh firmware/test_native.sh
```

Six scenarios exercise boot inhibition and every arming prerequisite, whole-frame
rejection, speed/joint/nonfinite limits, command timeout, unsigned-clock wrap,
sensor loss, latched faults/emergency stop and disarmed target rejection.

The request parser has separate native tests against the actual pinned
ArduinoJson headers, covering valid requests, malformed JSON, duplicate keys,
extra/trailing content, sequence/version bounds, nonfinite values and frame size:

```bash
sh firmware/test_protocol.sh
```

That script uses `.pio/libdeps/esp32dev/ArduinoJson/src` after normal dependency
installation, or a supplied `ARDUINOJSON_INCLUDE_DIR`. In this cloud instance,
it was run using upstream ArduinoJson `v7.3.1` headers (commit
`e03d8ae8857098b377fb5c95b9b2357ebf15ddff`) fetched over GitHub, with no board
or motor output involved. Native policy and protocol tests passed.

ESP32 compile (no hardware or upload required):

```bash
python -m venv .venv-firmware
.venv-firmware/bin/python -m pip install platformio==6.1.18
PLATFORMIO_CORE_DIR=/tmp/microduck-platformio .venv-firmware/bin/pio run -d firmware
```

The platform and ArduinoJson versions are pinned in `platformio.ini`.
An ESP32 compile was attempted in this cloud instance but the PlatformIO
registry hosts (`api.registry.platformio.org`, `registry.platformio.org`) were
blocked by the network proxy with HTTP 403. PlatformIO Core 6.1.18 installed,
but the ESP32 platform/toolchain could not be downloaded; **the ESP32 target
build is not verified here**. Enable the required dependency hosts in the
development environment or build with an already-installed trusted toolchain,
then rerun the compile before bench deployment. TLS/checksum checks were not
disabled or bypassed.

Do not add an automatic upload or motor-enable task. Real pin behavior, power
interlocks, I2C behavior, UART wiring and timing still require bench validation
with the servo supply disconnected. Native tests do not validate physical
hardware, and compiling firmware is not a motor commissioning result.
