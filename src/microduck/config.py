"""Load the reviewed hardware plan without treating example limits as calibration."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

JOINT_NAMES = (
    "left_hip_pitch", "left_knee", "left_ankle_pitch",
    "right_hip_pitch", "right_knee", "right_ankle_pitch", "head_pan", "head_tilt",
)


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class Joint:
    name: str
    channel: int
    minimum: float
    maximum: float
    neutral: float
    max_velocity: float


@dataclass(frozen=True)
class RobotConfig:
    joints: tuple[Joint, ...]
    tick_hz: float
    watchdog_ms: float

    @property
    def neutral(self):
        return {joint.name: joint.neutral for joint in self.joints}

    def validate_positions(self, positions):
        if not isinstance(positions, dict) or set(positions) != set(JOINT_NAMES):
            raise ValueError("positions must specify exactly all eight named joints")
        result = {}
        for joint in self.joints:
            value = number(positions[joint.name], joint.name)
            if not joint.minimum <= value <= joint.maximum:
                raise ValueError(f"{joint.name} exceeds simulation limits")
            result[joint.name] = value
        return result


def load_config(path: str | Path) -> RobotConfig:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("robot configuration must be a JSON object")
    if not isinstance(data.get("joints"), list) or not all(isinstance(j, dict) for j in data["joints"]):
        raise ValueError("joints must be a list of joint objects")
    if not isinstance(data.get("control"), dict):
        raise ValueError("control must be an object")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1 or type(data.get("initial_dof")) is not int or data["initial_dof"] != 8:
        raise ValueError("only the version 1 eight-joint design is supported")
    if data.get("default_backend") != "simulation" or data.get("hardware_output_enabled") is not False:
        raise ValueError("this scaffold supports simulation only; physical outputs must stay disabled")
    if data.get("balance_verified") is not False:
        raise ValueError("balance has not been verified for this design")
    joints = []
    for raw in data["joints"]:
        channel = raw["channel"]
        if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 15:
            raise ValueError("PCA9685 channel must be an integer from 0 to 15")
        low, high = [number(v, "joint limit") for v in raw["simulation_limits_deg"]]
        neutral = number(raw["simulation_neutral_deg"], "simulation neutral")
        velocity = number(raw["max_velocity_deg_s"], "velocity")
        if not low < high or not low <= neutral <= high or velocity <= 0:
            raise ValueError("invalid joint limits, neutral or velocity")
        joints.append(Joint(raw["name"], channel, low, high, neutral, velocity))
    if len(joints) != 8 or {j.name for j in joints} != set(JOINT_NAMES):
        raise ValueError("exactly the eight documented joints are required")
    if len({j.channel for j in joints}) != 8:
        raise ValueError("servo channels must be unique")
    if {j.name: j.channel for j in joints} != dict(zip(JOINT_NAMES, range(8))):
        raise ValueError("channel map must match the firmware protocol")
    hz = number(data["control"]["tick_hz"], "tick_hz")
    watchdog = number(data["control"]["watchdog_ms"], "watchdog_ms")
    for key, expected in (("protocol_version", 1), ("command_max_bytes", 512), ("serial_baud", 115200)):
        if type(data["control"].get(key)) is not int or data["control"][key] != expected:
            raise ValueError(f"{key} must match the firmware protocol ({expected})")
    if not 1 <= hz <= 200 or not 100 <= watchdog <= 2000:
        raise ValueError("unsupported control rate or watchdog timeout")
    return RobotConfig(tuple(joints), hz, watchdog)
