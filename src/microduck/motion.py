"""A kinematic joint interpolator, not a dynamics simulator or balance controller."""
from dataclasses import dataclass
from enum import Enum
import time
from typing import Protocol

from .config import RobotConfig, number


class State(str, Enum):
    DISARMED = "disarmed"
    ARMED = "armed"
    ESTOP = "estop"
    FAULT = "fault"


@dataclass(frozen=True)
class Feedback:
    positions_deg: dict[str, float]
    simulated: bool
    imu_valid: bool = False


class MotionBackend(Protocol):
    """Future hardware adapters must implement this boundary after commissioning."""
    is_simulation: bool

    def write_positions(self, positions: dict[str, float]) -> None: ...
    def read_feedback(self) -> Feedback: ...


class SimulatedBackend:
    is_simulation = True

    def __init__(self, config: RobotConfig):
        self._config = config
        self._positions = config.neutral

    def write_positions(self, positions):
        self._positions = self._config.validate_positions(positions)

    def read_feedback(self):
        # This is commanded joint state, not sensor telemetry or an IMU reading.
        return Feedback(dict(self._positions), simulated=True, imu_valid=False)


class MotionController:
    def __init__(self, config: RobotConfig, backend: MotionBackend, clock=time.monotonic):
        # Require the known simulation implementation, not just a caller-supplied flag.
        if type(backend) is not SimulatedBackend:
            raise ValueError("real motor adapters are intentionally unsupported in this scaffold")
        self.config, self.backend, self.clock = config, backend, clock
        self.state = State.DISARMED
        self._target = config.neutral
        self._positions = config.neutral
        self._last_command = None

    def arm_simulation(self):
        if self.state is not State.DISARMED:
            raise RuntimeError(f"cannot arm from {self.state.value}; create a new simulation after a latch")
        self.state = State.ARMED
        self._target = dict(self._positions)
        self._last_command = self.clock()

    def disarm(self):
        if self.state is State.ARMED:
            self.state = State.DISARMED
        self._target = dict(self._positions)

    def estop(self):
        self.state = State.ESTOP
        self._target = dict(self._positions)

    def _check_watchdog(self):
        if self.state is State.ARMED and self.clock() - self._last_command >= self.config.watchdog_ms / 1000:
            self.state = State.FAULT
            raise RuntimeError("command watchdog expired; simulation is latched off")

    def set_target(self, positions):
        self._check_watchdog()
        if self.state is not State.ARMED:
            raise RuntimeError("simulation is not armed")
        self._target = self.config.validate_positions(positions)
        self._last_command = self.clock()

    def tick(self, dt_s):
        dt = number(dt_s, "dt_s")
        if not 0 < dt <= 1 / self.config.tick_hz + 1e-9:
            raise ValueError("dt must be positive and no greater than one control period")
        self._check_watchdog()
        if self.state is not State.ARMED:
            raise RuntimeError("simulation is not armed")
        positions = {}
        for joint in self.config.joints:
            delta = self._target[joint.name] - self._positions[joint.name]
            step = joint.max_velocity * dt
            positions[joint.name] = self._positions[joint.name] + max(-step, min(step, delta))
        self.backend.write_positions(positions)
        self._positions = positions
        return self.backend.read_feedback()
