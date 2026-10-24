"""Parametric MicroDuck visual concept. Units: mm; +X forward, +Y left, +Z up.

This is a newly constructed solid CAD interpretation, not production hardware.
Reference: Pollen Robotics, github.com/pollen-robotics/microduck_rl.
Model geometry: CC BY-NC-SA 4.0; see README.md and reference/ attribution.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import struct

import cadquery as cq
import numpy as np


@dataclass(frozen=True)
class Parameters:
    scale: float = 1.0
    head_depth: float = 122.0
    head_width: float = 92.0
    head_arch_height: float = 43.0
    head_base_z: float = 231.0
    head_back_x: float = -47.0
    shell_wall: float = 2.8
    torso_depth: float = 80.0
    torso_width: float = 64.0
    torso_height: float = 42.0
    foot_depth: float = 54.0
    foot_width: float = 40.0
    foot_spacing: float = 85.0
    eye_outer_radius: float = 15.0
    eye_inner_radius: float = 9.0


COLORS = {
    "ivory": (0.88, 0.885, 0.86),
    "orange": (1.0, 0.36, 0.075),
    "yellow": (0.96, 0.68, 0.13),
    "dark": (0.13, 0.15, 0.16),
    "motor": (0.24, 0.26, 0.27),
    "metal": (0.61, 0.63, 0.62),
    "taupe": (0.59, 0.57, 0.52),
    "face": (0.29, 0.30, 0.29),
    "glass": (0.035, 0.08, 0.105),
}


def rounded_box(size, center, radius=2.0):
    radius = min(radius, min(size) * 0.49)
    return (cq.Workplane("XY").box(*size).edges().fillet(radius)
            .translate(center).val())


def cylinder(radius, length, start, direction):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*start), cq.Vector(*direction))


def ring(radius, bore, length, start, direction):
    return cylinder(radius, length, start, direction).cut(
        cylinder(bore, length, start, direction))


def arch(width, height, length, back_x, base_z):
    """A true elliptical roof profile with a flat base; extrusion along X."""
    return (cq.Workplane("YZ", origin=(back_x, 0, base_z))
            .moveTo(width / 2, 0)
            .ellipseArc(width / 2, height, angle1=0, angle2=180)
            .close().extrude(length).val())


def link(a, b, width, thickness, y, hole=3.0):
    """Rounded strap in the XZ plane, with two actual through-holes."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    plane = cq.Plane(origin=(0, y + thickness / 2, 0),
                     xDir=(1, 0, 0), normal=(0, -1, 0))
    result = (cq.Workplane(plane)
              .center((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
              .slot2D(math.hypot(dx, dz) + width, width,
                      math.degrees(math.atan2(dz, dx)))
              .extrude(thickness).val())
    for x, z in (a, b):
        result = result.cut(cylinder(hole, thickness + 2,
                            (x, y - thickness / 2 - 1, z), (0, 1, 0)))
    return result


def build(p=Parameters()):
    """Return a color assembly and a list of independently editable BREP parts."""
    parts = []

    def add(name, shape, material):
        if not shape.isValid() or not shape.Solids() or shape.Volume() <= 0:
            raise ValueError(f"Invalid or empty solid: {name}")
        if p.scale != 1:
            shape = shape.scale(p.scale)
        parts.append((name, shape, material))

    # The characteristic long arched hood is hollow, with an open front and
    # an enclosed back. The orange lower tray closes the underside visually.
    head = arch(p.head_width, p.head_arch_height, p.head_depth,
                p.head_back_x, p.head_base_z)
    cavity = arch(p.head_width - 2 * p.shell_wall,
                  p.head_arch_height - p.shell_wall,
                  p.head_depth + 2, p.head_back_x + p.shell_wall,
                  p.head_base_z - 0.1)
    add("head_arched_hood", head.cut(cavity), "ivory")
    add("head_face_insert", arch(p.head_width - 7, p.head_arch_height - 4,
        3, p.head_back_x + p.head_depth - 15, p.head_base_z), "face")

    jaw_z = p.head_base_z - 8.0
    jaw = rounded_box((p.head_depth - 4, p.head_width, 16),
                       (p.head_back_x + p.head_depth / 2 - 2, 0, jaw_z), 5)
    jaw_void = rounded_box((p.head_depth - 13, p.head_width - 8, 14),
                           (p.head_back_x + p.head_depth / 2 - 2, 0, jaw_z + 4), 3)
    add("orange_lower_jaw", jaw.cut(jaw_void), "orange")
    front = p.head_back_x + p.head_depth
    add("mouth_dark_seam", rounded_box((2, p.head_width - 9, 2),
        (front - 3.5, 0, p.head_base_z + 0.3), 0.6), "dark")
    add("mouth_upper_lip", rounded_box((3, p.head_width - 7, 2.4),
        (front - 3.1, 0, p.head_base_z + 2.1), 0.8), "orange")

    eye_z = p.head_base_z + 18
    add("single_yellow_camera_bezel", ring(p.eye_outer_radius,
        p.eye_inner_radius, 8, (front - 11, 0, eye_z), (1, 0, 0)), "yellow")
    add("camera_black_barrel", cylinder(p.eye_inner_radius - 0.15, 9.5,
        (front - 12, 0, eye_z), (1, 0, 0)), "dark")
    add("camera_glass", cylinder(p.eye_inner_radius - 1.6, 0.7,
        (front - 2.5, 0, eye_z), (1, 0, 0)), "glass")
    # Two jaw pivot tabs and visible hardware, in the same plane as the shell.
    for side, label in ((-1, "right"), (1, "left")):
        y = side * (p.head_width / 2 - 1.5)
        tab = link((0, p.head_base_z - 5), (-9, p.head_base_z + 8),
                   14, 3, y, hole=1.6)
        add(f"jaw_pivot_tab_{label}", tab, "orange")
        add(f"jaw_pivot_pin_{label}", cylinder(1.5, 5,
            (-9, y - 2.5, p.head_base_z + 8), (0, 1, 0)), "metal")

    # Compact oval torso, left/right shell seam, battery and neck cutout.
    torso_center = (-6, 0, 141)
    torso_outer = rounded_box((p.torso_depth, p.torso_width, p.torso_height),
                              torso_center, 11)
    torso_inner = rounded_box((p.torso_depth - 6, p.torso_width - 6,
                               p.torso_height - 6), torso_center, 8)
    torso = torso_outer.cut(torso_inner)
    throat = rounded_box((36, 32, 30), (19, 0, 163), 5)
    torso = torso.cut(throat)
    # The divider leaves a small visible center seam without moving the halves.
    left_clip = cq.Workplane("XY").box(200, 100, 150).translate((0, 50.3, 140)).val()
    right_clip = cq.Workplane("XY").box(200, 100, 150).translate((0, -50.3, 140)).val()
    add("torso_shell_left", torso.intersect(left_clip), "ivory")
    add("torso_shell_right", torso.intersect(right_clip), "ivory")
    add("torso_inner_frame", rounded_box((56, 33, 8), (-3, 0, 122), 2), "dark")
    add("rear_battery_pack", rounded_box((21, 38, 67), (-36, 0, 113), 3), "motor")
    for y in (-22, 22):
        for x in (-32, 19):
            add(f"torso_screw_{x}_{y}", cylinder(2.4, 1.2,
                (x, y, 159.8), (0, 0, 1)), "metal")

    # Exposed two-sided neck; unlike a duck ornament there are no wings/arms.
    neck_bottom, neck_top = (26, 156), (9, 202)
    for y, label in ((-13, "right"), (13, "left")):
        add(f"neck_link_{label}", link(neck_bottom, neck_top, 14, 3, y), "taupe")
    add("neck_lower_servo", rounded_box((25, 24, 27), (24, 0, 160), 1.5), "motor")
    add("neck_upper_servo", rounded_box((25, 24, 25), (9, 0, 199), 1.5), "motor")
    add("neck_center_brace", rounded_box((16, 30, 8), (17, 0, 180), 1.2), "metal")
    for idx, (x, z) in enumerate((neck_bottom, neck_top)):
        add(f"neck_axle_{idx}", cylinder(3, 33, (x, -16.5, z), (0, 1, 0)), "metal")
        for side in (-1, 1):
            add(f"neck_horn_{idx}_{side}", ring(10, 3, 2.5,
                (x, side * 14 - 1.25, z), (0, 1, 0)), "metal")
    add("head_yaw_gimbal", rounded_box((28, 30, 14), (8, 0, 214), 3), "dark")
    add("head_mount_plate", rounded_box((39, 36, 4), (8, 0, 217), 2), "taupe")

    # Mirrored, articulated-looking legs and rounded flat boots.
    for side, label in ((-1, "right"), (1, "left")):
        fy = side * p.foot_spacing / 2
        hip, knee, ankle = (3, 109), (-23, 69), (1, 26)
        add(f"hip_yaw_servo_{label}", rounded_box((27, 25, 26),
            (3, side * 28, 113), 2), "dark")
        add(f"hip_outer_servo_{label}", rounded_box((27, 24, 29),
            (3, side * 48, 108), 2), "motor")
        add(f"hip_cross_axle_{label}", cylinder(5, 32,
            (3, side * 38 - 16, 109), (0, 1, 0)), "metal")
        add(f"thigh_outer_plate_{label}", link(hip, knee, 24, 6,
            side * 63, hole=3.0), "ivory")
        add(f"thigh_inner_plate_{label}", link(hip, knee, 15, 4,
            side * 41, hole=3.0), "taupe")
        add(f"knee_servo_{label}", rounded_box((27, 23, 23),
            (knee[0], side * 51, knee[1]), 2), "motor")
        add(f"shin_outer_link_{label}", link(knee, ankle, 11, 4,
            side * 44, hole=3.0), "taupe")
        add(f"shin_inner_link_{label}", link(knee, ankle, 11, 4,
            side * 32, hole=3.0), "metal")
        add(f"ankle_servo_{label}", rounded_box((24, 25, 27),
            (1, fy, 29), 2), "motor")
        for index, (x, z) in enumerate((hip, knee, ankle)):
            axis_y = side * (51 if index < 2 else 42.5)
            add(f"joint_axle_{label}_{index}", cylinder(3, 33,
                (x, axis_y - 16.5, z), (0, 1, 0)), "metal")
            add(f"joint_bearing_{label}_{index}", ring(8.5, 3.1, 2.5,
                (x, side * (66 if index < 2 else 55) - 1.25, z), (0, 1, 0)), "metal")
        add(f"foot_sole_{label}", rounded_box((p.foot_depth, p.foot_width, 5),
            (7, fy, 2.5), 2.3), "yellow")
        boot = rounded_box((p.foot_depth, p.foot_width, 12), (7, fy, 10), 4.5)
        for y in (fy - 14, fy + 14):
            boot = boot.fuse(link((-8, 13), (1, 26), 18, 4, y, hole=4.3))
        add(f"orange_foot_{label}", boot, "orange")
        for y in (fy - 11, fy + 11):
            add(f"foot_deck_screw_{label}_{int(y)}", cylinder(1.9, 1,
                (24, y, 15.4), (0, 0, 1)), "metal")

    assembly = cq.Assembly(name="MicroDuck_parametric_concept")
    for name, shape, material in parts:
        assembly.add(shape, name=name, color=cq.Color(*COLORS[material]))
    return assembly, parts


def export_stl(shape, path):
    """Discard OCCT's collapsed pole triangles, preserving the solid surface."""
    cq.exporters.export(shape, str(path), tolerance=0.13, angularTolerance=0.12)
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)),
                      ("attribute", "<u2")])
    facets = np.frombuffer(data, dtype=dtype, count=count, offset=84)
    vertices = facets["vertices"].astype(np.float64)
    doubled_area = np.linalg.norm(np.cross(vertices[:, 1] - vertices[:, 0],
                                           vertices[:, 2] - vertices[:, 0]), axis=1)
    facets = facets[doubled_area > 1e-10]
    path.write_bytes(data[:80] + struct.pack("<I", len(facets)) + facets.tobytes())


def glb_millimeters_to_meters(path):
    """CadQuery 2.7 exports mm positions; glTF requires world units in meters."""
    data = path.read_bytes()
    length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError("Expected a JSON GLB chunk")
    model = json.loads(data[20:20 + length])
    roots = {node for scene in model["scenes"] for node in scene["nodes"]}
    for node in roots:
        if "matrix" in model["nodes"][node]:
            raise ValueError("Unexpected matrix root; cannot combine glTF transforms")
        model["nodes"][node]["scale"] = [0.001, 0.001, 0.001]
    encoded = json.dumps(model, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    tail = data[20 + length:]
    total = 12 + 8 + len(encoded) + len(tail)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, total)
                     + struct.pack("<II", len(encoded), chunk_type) + encoded + tail)


def export(output, p):
    output.mkdir(parents=True, exist_ok=True)
    part_dir = output / "parts"
    part_dir.mkdir(exist_ok=True)
    assembly, parts = build(p)
    assembly.export(str(output / "microduck.step"), "STEP")
    assembly.export(str(output / "microduck.glb"), "GLTF", tolerance=0.13, angularTolerance=0.12)
    glb_millimeters_to_meters(output / "microduck.glb")
    compound = cq.Compound.makeCompound([shape for _, shape, _ in parts])
    export_stl(compound, output / "microduck.stl")
    records = []
    for name, shape, material in parts:
        export_stl(shape, part_dir / f"{name}.stl")
        bb = shape.BoundingBox()
        records.append(dict(name=name, material=material, solids=len(shape.Solids()),
                            volume_mm3=round(shape.Volume(), 3), valid=shape.isValid(),
                            bounds_mm=[[bb.xmin, bb.ymin, bb.zmin], [bb.xmax, bb.ymax, bb.zmax]]))
    bb = compound.BoundingBox()
    manifest = dict(model="MicroDuck parametric visual concept", units="mm",
        axes="+X forward, +Y left, +Z up", parameters=asdict(p),
        dimensions_mm=dict(depth=round(bb.xlen, 3), width=round(bb.ylen, 3), height=round(bb.zlen, 3)),
        part_count=len(parts), solid_count=len(compound.Solids()),
        license="CC BY-NC-SA 4.0", parts=records,
        limitations="Visual concept; servo envelopes, fasteners, joints and fit are not hardware-validated. Assembly STL contains separate overlapping closed solids; use STEP for CAD and individual STLs for print preparation.")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("part_count", "solid_count", "dimensions_mm")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "exports")
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()
    if args.scale <= 0:
        parser.error("--scale must be positive")
    export(args.output, Parameters(scale=args.scale))
