# Development roadmap

Progress is gated by evidence, not dates. Initial hardware target: roughly
$200 of parts for an eight-servo, externally supported bench prototype.

| Phase | Work | Acceptance evidence |
|---|---|---|
| 0 — Repository and simulation | Validate configuration, command boundaries and safety state; keep hardware output disabled | Python tests and native firmware tests pass; simulation runs without devices, network or credentials |
| 1 — Mechanical feasibility | Redesign the visual CAD for eight candidate servos, printed fits, wiring and mass; measure lever arms and choose actual actuators | Mounting coupon fits real hardware; mass/torque estimate with margin; interference and supported range checked; updated BOM stays within an agreed budget |
| 2 — Logic bench | Pi↔ESP32 UART, MPU6050 raw readings, reset behavior and independent power disconnect, no servos | Recorded serial/sensor checks; malformed/disconnected links stay inhibited; electrical gate/OE/stop behavior measured |
| 3 — Commissioning implementation | Add calibrated output module, measured limits, authorization and fault handling | Tests cover refusal of missing calibration/interlocks; independent physical stop proven; no automatic arm after reset or reconnect |
| 4 — Individual joints | Calibrate one unloaded servo at a time and recheck under controlled load | Per-servo measured calibration, current/thermal observations and load suitability; no hard-stop contact; all eight channels verified |
| 5 — Supported robot | Assemble under external support; use bounded joint commands only | No interference; measured rail stability; watchdog, disarm, reset and physical stop remove servo power correctly |
| 6 — Pi perception and voice | Add camera provider, microphone and audio output, then optional cloud client | Camera/audio resource and power measurements; bounded cloud timeouts; provider failures cannot actuate or arm motors; no secrets in Git |
| 7 — Balance feasibility research | Determine whether pitch-only legs are viable or add lateral joints/redesign | Quantified kinematics, contact and center-of-mass model; externally supported control experiments; explicit independent criteria before claiming standing |

No gait or self-balancing capability is promised by this scaffold. A six-leg-
servo layout omits hip and ankle roll, which restricts lateral control. At this
budget, reducing mass/height or building a supported demonstrator may be the
correct first result; a larger visual resemblance cannot override torque and
power measurements.

Start with joint moment estimates `torque ≈ supported_mass × g × lever_arm`,
including link weights, geometry and a margin for real motion. Servo stall
torque is not a continuous operating rating. Compare estimates to measured or
credible continuous capability rather than relying on nominal low-cost servo
labels. Re-budget before purchasing upgrades.

Battery power, charger selection, untethered operation, dynamic locomotion,
fall recovery and reinforcement learning are later projects. They are excluded
from the initial budget and readiness claims. Preserve the original CAD and
license attribution while evolving a separately validated mechanical design.
