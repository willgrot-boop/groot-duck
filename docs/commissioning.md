# Commissioning gates

**The current scaffold does not authorize real servo output.** It has no
runtime hardware-arming/PWM implementation, and calibration values start null.
Do not connect servo power while running its examples. Editing a Boolean is
not a commissioning procedure.

Record each check, operator, date, measured result and relevant component
revision in a local commissioning log before progressing. This file is a plan,
not evidence that any check has already passed.

## 1. Software and unpowered inspection

- Run Python simulation and native firmware tests; compile the ESP32 target.
- Confirm all eight names/channels match `hardware/robot.json`.
- Inspect printed parts, horn screws, sharp edges and wire strain relief.
- Determine whether the lighter eight-servo design fits and has adequate
  torque. The archived 71-part visual CAD model does not establish this.
- Keep motor power disconnected; remove servo horns where practical.

## 2. Logic-only electronics

- Verify separate positive supply rails, common ground, polarity and fuse plan.
- Confirm no 5 V reaches UART/I2C/GPIO and no USB/backfeed path exists.
- Power logic only. Read firmware status, then test malformed frames,
  sequence handling, disconnects, watchdog behavior and software estop.
- Validate IMU identity, wiring, raw data changes and failure reporting.
  Calibrate bias/orientation later; raw readings are not an attitude estimate.
- Verify gate off and OE high on boot, reset, flashing and communication loss.

## 3. Independent power removal

- With no servos connected, check the physical latching stop opens the servo
  rail independently of software. Verify its current rating and reset behavior.
- Confirm a stopped/reset/unplugged controller cannot re-energize motor power.
- Plan current measurement, current limiting, suitable fuses and a fixture.
  Do not choose fuse and wire ratings solely from the $200 cost estimate.

## 4. Implement and review the missing commissioning module

Before any servo can be driven, implement measured calibration loading,
validated per-channel pulse bounds and direction, physical stop feedback or a
verified equivalent interlock, rail monitoring/current policy, explicit local
operator authorization, output ordering and fault-injection tests. Review how
reset, brownout, I2C failure and UART loss remove power. Only then can the
firmware support a dedicated commissioning path. Cloud commands cannot supply
that authorization.

## 5. One-servo calibration, later hardware phase

After all previous gates pass, use a separate stable fixture, conservative
current limiting and a ready physical stop. Work with one unloaded joint and
small measured changes. Establish the individual servo's pulse direction,
mechanical clearance, center, usable endpoints and load/current behavior.
Stop before hard contact, heating, excessive current or buzzing. Do not assume
a generic advertised 500–2500 µs range is safe, and do not guess pulse values
to fill the template. Record the measured values with the servo identity.

Repeat individually for all channels. Mount horns only after orientation and
mechanical clearance are verified. Recheck limits after assembly. Simulation
neutrals and limits must be replaced with measured hardware constraints in
the commissioning implementation; no automatic degree-to-pulse map exists now.

## 6. Supported assembly before balance research

Suspend or externally support the robot so an unexpected joint change cannot
cause a fall. Demonstrate predictable bounded joint positioning, controlled
power loss, command timeout, stop recovery and cable routing under support.
Observe logic supply droop with camera/audio active and servos loaded. A camera
demo, a servo sweep or an IMU stream is not proof of standing or balance.

Unassisted standing, walking and cloud-triggered behavior remain out of scope
until a validated mechanical/control design and separate acceptance tests
exist. The initial pitch-only leg layout may require revision for lateral
control. Never set `balance_verified` merely because a simulated pose ran.
