# Eight-servo bench prototype

The hardware target is a Raspberry Pi Zero 2 W plus a **classic ESP32 DevKit**,
six leg servos and two head servos. This is a proposed bill of materials and
interface plan, not a tested robot or a claim that it can stand or walk.

- [`robot.json`](robot.json): board pins, addresses, channels and simulation limits.
- [`calibration.example.json`](calibration.example.json): intentionally unusable
  hardware calibration template; every measured value starts as `null`.
- [`bom.csv`](bom.csv): machine-readable **$200 USD estimated parts budget**.
- [Wiring](../docs/wiring.md), [commissioning](../docs/commissioning.md),
  [architecture](../docs/architecture.md), [roadmap](../docs/roadmap.md).

The BOM is a planning estimate, not current vendor quotes. It includes $5 of
contingency and an initial mains-powered bench supply, but excludes shipping,
tax, tools, printer purchase, cloud API usage and battery operation. Print
service and servo prices can exceed these allowances. Price components before
ordering; upgrade or reduce the design if torque or current measurements fail.

MG90S is a candidate low-cost servo family, not a validated selection. Clone
quality, voltage, travel, pulse response, peak current and usable torque vary.
Do not substitute the old reference robot's Dynamixel geometry or parameters.
The archived CAD is a visual design; it does not establish eight-servo mounting
fits, clearances, structure, torque capacity or a center of mass.

## Channel map

| PCA9685 channel | Joint | Function |
|---|---|---|
| 0 | `left_hip_pitch` | Left leg forward/back |
| 1 | `left_knee` | Left knee flexion |
| 2 | `left_ankle_pitch` | Left ankle pitch |
| 3 | `right_hip_pitch` | Right leg forward/back |
| 4 | `right_knee` | Right knee flexion |
| 5 | `right_ankle_pitch` | Right ankle pitch |
| 6 | `head_pan` | Head yaw |
| 7 | `head_tilt` | Head pitch |

This allocation deliberately has **no hip-roll or ankle-roll joints**. Lateral
balance may require a different mechanical design, wider supported feet,
additional degrees of freedom or a support fixture. The scaffold does not
implement balance, gait generation or reinforcement learning.

`simulation_limits_deg`, neutral angles and velocity limits are examples for
testing software. They are not measured motor endpoints. The JSON flags remain
`hardware_output_enabled: false` and `balance_verified: false`.

The firmware has no operational commissioning/PWM path in this revision.
Setting a JSON flag or filling the template does not enable real servos.
