import csv
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from microduck.config import JOINT_NAMES, load_config
from microduck.motion import MotionController, SimulatedBackend, State
from microduck.protocol import decode_request, encode_request
from microduck.services import Action, action_target, validate_proposal

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "hardware/robot.json"


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG)

    def modified(self, change):
        data = json.loads(CONFIG.read_text())
        change(data)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "robot.json"
            path.write_text(json.dumps(data))
            return load_config(path)

    def test_eight_joints_have_unique_firmware_channels(self):
        self.assertEqual({j.name: j.channel for j in self.config.joints}, dict(zip(JOINT_NAMES, range(8))))

    def test_unsafe_backend_and_enabled_output_rejected(self):
        for change in (lambda d: d.update(default_backend="serial"),
                       lambda d: d.update(hardware_output_enabled=True),
                       lambda d: d.update(balance_verified=True)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.modified(change)

    def test_invalid_channel_and_joint_count_rejected(self):
        for change in (lambda d: d["joints"][0].update(channel=True),
                       lambda d: d["joints"][1].update(channel=0),
                       lambda d: d["joints"].pop(),
                       lambda d: d["joints"][0].update(channel=15)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.modified(change)

    def test_invalid_limits_and_protocol_mismatch_rejected(self):
        for change in (lambda d: d["joints"][0].update(simulation_limits_deg=[0, 0]),
                       lambda d: d["joints"][0].update(max_velocity_deg_s=-1),
                       lambda d: d["joints"][0].update(simulation_neutral_deg=100),
                       lambda d: d["control"].update(command_max_bytes=2048)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.modified(change)

    def test_full_named_targets_only(self):
        target = self.config.neutral
        for bad in ({}, {**target, "wing": 1}, {"head_pan": 1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.config.validate_positions(bad)

    def test_nonfinite_bool_and_out_of_range_angles_rejected(self):
        for bad in (float("nan"), float("inf"), True, "1", 61, 10 ** 400):
            target = self.config.neutral
            target["head_pan"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.config.validate_positions(target)

    def test_malformed_config_containers_fail_cleanly(self):
        for change in (lambda d: d.update(joints=[None]),
                       lambda d: d.update(control=[]),
                       lambda d: d.update(joints=None)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.modified(change)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.json"
            path.write_text("[]")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_budget_and_calibration_are_honest(self):
        with (ROOT / "hardware/bom.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        total = Decimal("0")
        for row in rows:
            expected = Decimal(row["unit_usd"]) * Decimal(row["quantity"])
            self.assertEqual(expected, Decimal(row["subtotal_usd"]))
            total += expected
        self.assertGreaterEqual(total, Decimal("180"))
        self.assertLessEqual(total, Decimal("220"))
        calibration = json.loads((ROOT / "hardware/calibration.example.json").read_text())
        self.assertIs(calibration["calibrated"], False)
        self.assertIs(calibration["bench_checks_passed"], False)
        self.assertEqual(len(calibration["joints"]), 8)
        for joint in calibration["joints"]:
            self.assertIs(joint["calibrated"], False)
            self.assertIsNone(joint["pwm_neutral_us"])


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG)
        self.now = 0
        self.backend = SimulatedBackend(self.config)
        self.controller = MotionController(self.config, self.backend, clock=lambda: self.now)

    def test_boot_disarmed_and_hardware_adapter_rejected(self):
        self.assertEqual(self.controller.state, State.DISARMED)
        with self.assertRaises(RuntimeError):
            self.controller.tick(0.02)
        class PretendHardware:
            is_simulation = True
        with self.assertRaises(ValueError):
            MotionController(self.config, PretendHardware())

    def test_target_interpolates_without_teleporting(self):
        self.controller.arm_simulation()
        target = self.config.neutral
        target["head_pan"] = 30
        self.controller.set_target(target)
        feedback = self.controller.tick(0.02)
        self.assertAlmostEqual(feedback.positions_deg["head_pan"], 1.2)
        self.assertTrue(feedback.simulated)
        self.assertFalse(feedback.imu_valid)
        self.assertEqual(feedback.positions_deg["left_knee"], 20)

    def test_estop_latches_and_preserves_position(self):
        self.controller.arm_simulation()
        before = self.backend.read_feedback()
        self.controller.estop()
        self.controller.disarm()
        with self.assertRaises(RuntimeError):
            self.controller.arm_simulation()
        with self.assertRaises(RuntimeError):
            self.controller.set_target(self.config.neutral)
        self.assertEqual(before, self.backend.read_feedback())

    def test_watchdog_latches_even_when_new_target_arrives(self):
        self.controller.arm_simulation()
        self.now = 0.5
        with self.assertRaises(RuntimeError):
            self.controller.set_target(self.config.neutral)
        self.assertEqual(self.controller.state, State.FAULT)
        self.controller.disarm()
        with self.assertRaises(RuntimeError):
            self.controller.arm_simulation()

    def test_oversized_or_invalid_tick_cannot_bypass_rate_limit(self):
        self.controller.arm_simulation()
        for dt in (0, -1, 1, True, float("nan")):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                self.controller.tick(dt)

    def test_feedback_mutation_does_not_change_backend(self):
        feedback = self.backend.read_feedback()
        feedback.positions_deg["head_pan"] = 60
        self.assertEqual(self.backend.read_feedback().positions_deg["head_pan"], 0)

    def test_invalid_target_is_atomic(self):
        self.controller.arm_simulation()
        target = self.config.neutral
        target["head_pan"] = 500
        with self.assertRaises(ValueError):
            self.controller.set_target(target)
        self.assertEqual(self.controller.tick(0.02).positions_deg, self.config.neutral)


class ProtocolAndServicesTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG)

    def test_wire_round_trip(self):
        request = encode_request("target", 4, self.config, self.config.neutral)
        self.assertLessEqual(len(request) - 1, 512)
        decoded = decode_request(request, self.config)
        self.assertEqual(decoded["positions_deg"], self.config.neutral)
        self.assertEqual(decoded["seq"], 4)

    def test_bad_frames_are_rejected(self):
        for line in (b'{}', b'{}\n{}\n', b' ' * 513 + b'\n',
                     b'{"v":1,"v":1,"seq":0,"type":"status"}\n',
                     b'{"v":true,"seq":0,"type":"status"}\n',
                     b'{"v":1,"seq":-1,"type":"status"}\n',
                     b'{"v":1,"seq":0,"type":"walk"}\n',
                     b'{"v":1,"seq":0,"type":"status","extra":0}\n',
                     b'{"v":1,"seq":0,"type":"target","positions_deg":{}}\n',
                     b'{"v":1,"seq":0,"type":"target","positions_deg":{"head_pan":NaN}}\n'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                decode_request(line, self.config)

    def test_untrusted_cloud_proposals_have_small_allowlist(self):
        for proposal in ("walk", "balance", "exec('bad')", '{"pwm":2500}'):
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                validate_proposal(proposal)
        action = validate_proposal("look_left")
        target = action_target(action, self.config.neutral)
        self.assertEqual(target["head_pan"], 10)
        self.config.validate_positions(target)
        with self.assertRaises(ValueError):
            action_target(Action.STOP, self.config.neutral)

    def test_cli_simulation_and_status_have_no_real_transport(self):
        result = subprocess.run([sys.executable, "-m", "microduck", "--config", str(CONFIG),
                                 "simulate", "--duration", "0.1"], capture_output=True, text=True, check=True)
        frames = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(frames), 5)
        self.assertTrue(all(f["simulated"] and not f["imu_valid"] for f in frames))
        self.assertEqual(frames[-1]["t_s"], 0.1)


if __name__ == "__main__":
    unittest.main()
