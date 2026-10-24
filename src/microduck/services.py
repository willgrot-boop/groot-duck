"""Pi service boundaries; camera/audio/cloud implementations are future work.

Cloud text never becomes arbitrary joint commands. This local allowlist is a
small, testable place to validate future planner proposals before motion logic.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


@dataclass(frozen=True)
class CameraFrame:
    jpeg: bytes
    timestamp_s: float


class Camera(Protocol):
    def capture(self) -> CameraFrame: ...


class VoiceInput(Protocol):
    def transcribe(self) -> str: ...


class CloudPlanner(Protocol):
    def propose_action(self, user_text: str) -> str: ...


class Action(str, Enum):
    STOP = "stop"
    LOOK_CENTER = "look_center"
    LOOK_LEFT = "look_left"
    LOOK_RIGHT = "look_right"


def validate_proposal(proposal: str) -> Action:
    """Reject gait, balancing, code execution and arbitrary pulse proposals."""
    return Action(proposal)


def action_target(action: Action, current: dict[str, float]):
    if not isinstance(action, Action):
        raise ValueError("planner proposal must be validated first")
    if action is Action.STOP:
        raise ValueError("stop must use the controller's latched estop, not a pose")
    target = dict(current)
    target["head_pan"] = {Action.LOOK_CENTER: 0, Action.LOOK_LEFT: 10, Action.LOOK_RIGHT: -10}[action]
    return target
