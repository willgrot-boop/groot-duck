"""Repository CLI: configuration inspection, bounded joint simulation, protocol output."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

from .config import load_config, number
from .motion import MotionController, SimulatedBackend
from .protocol import encode_request


def main(argv=None):
    parser = argparse.ArgumentParser(description="Microduck prototype: simulation only, no real motor output")
    parser.add_argument("--config", type=Path, default=Path("hardware/robot.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config")
    commands.add_parser("protocol-status", help="print a status request; does not open a serial port")
    sim = commands.add_parser("simulate", help="joint interpolation only; no gravity, contacts or balancing")
    sim.add_argument("--duration", type=float, default=1.0)
    sim.add_argument("--realtime", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "check-config":
            print(json.dumps({"backend": "simulation", "hardware_output_enabled": False,
                              "joint_count": len(config.joints), "balance_verified": False}))
        elif args.command == "protocol-status":
            print(encode_request("status", 1, config).decode(), end="")
        else:
            duration = number(args.duration, "duration")
            if not 0 < duration <= 60:
                raise ValueError("duration must be between 0 and 60 seconds")
            now = [0.0]
            controller = MotionController(config, SimulatedBackend(config), clock=lambda: now[0])
            controller.arm_simulation()
            dt = 1 / config.tick_hz
            try:
                for index in range(math.ceil(duration * config.tick_hz)):
                    target = config.neutral
                    target["head_pan"] = 8 * math.sin(now[0] * math.tau / 4)
                    controller.set_target(target)
                    feedback = controller.tick(dt)
                    print(json.dumps({"t_s": round(now[0] + dt, 6), "state": controller.state.value,
                                      **asdict(feedback)}))
                    now[0] = (index + 1) * dt
                    if args.realtime:
                        time.sleep(dt)
            finally:
                controller.disarm()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    return 0
