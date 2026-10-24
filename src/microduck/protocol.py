"""Version 1 UART JSON-lines codec. No port opening, PWM or hardware arming."""
import json

from .config import RobotConfig

MAX_BYTES = 512  # excludes the single line-feed terminator
TYPES = {"status", "disarm", "estop", "arm", "target"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_request(line: bytes, config: RobotConfig):
    if not isinstance(line, bytes) or not line.endswith(b"\n") or b"\n" in line[:-1]:
        raise ValueError("request must be one UTF-8 JSON line ending in LF")
    if len(line) - 1 > MAX_BYTES:
        raise ValueError("request exceeds 512 byte limit")
    obj = json.loads(line[:-1].decode("utf-8"), object_pairs_hook=_unique_object,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))
    if not isinstance(obj, dict) or type(obj.get("v")) is not int or obj["v"] != 1:
        raise ValueError("protocol v must be integer 1")
    if type(obj.get("seq")) is not int or not 0 <= obj["seq"] <= 2147483647:
        raise ValueError("seq must be a nonnegative 31-bit integer")
    if not isinstance(obj.get("type"), str) or obj["type"] not in TYPES:
        raise ValueError("unknown request type")
    expected = {"v", "seq", "type", "positions_deg"} if obj["type"] == "target" else {"v", "seq", "type"}
    if set(obj) != expected:
        raise ValueError("unexpected or missing request fields")
    if obj["type"] == "target":
        obj["positions_deg"] = config.validate_positions(obj["positions_deg"])
    return obj


def encode_request(kind, seq, config, positions=None):
    obj = {"v": 1, "seq": seq, "type": kind}
    if positions is not None:
        obj["positions_deg"] = positions
    line = json.dumps(obj, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    decode_request(line, config)
    return line
