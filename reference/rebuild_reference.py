#!/usr/bin/env python3
"""Rebuild the official Microduck reference assembly. Requires Python + numpy.

The source meshes are unmodified Pollen Robotics assets, CC BY-NC-SA 4.0.
This script applies the upstream STAND pose, converts units, and exports STL/GLB.
It does not generate a feature-based CAD model or a union for 3D printing.
"""
from pathlib import Path
import json
import struct

import numpy as np

ROOT = Path(__file__).resolve().parent


def read_stl(path):
    raw = path.read_bytes()
    count = struct.unpack_from("<I", raw, 80)[0]
    assert len(raw) == 84 + 50 * count, f"Invalid binary STL: {path}"
    record = np.dtype([("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])
    return np.frombuffer(raw, record, offset=84, count=count)["v"].astype(np.float64)


def main():
    data = json.loads((ROOT / "assembly.json").read_text())
    ground = float(data["bounds_mm"][0][2])
    objects = []
    for item in data["parts"]:
        triangles = read_stl(ROOT / item["stl_path"])
        points = triangles.reshape(-1, 3) * 1000 * item["mesh_scale"]
        transform = np.asarray(item["transform_mm"])
        points = points @ transform[:3, :3].T + transform[:3, 3]
        points[:, 2] -= ground
        assert np.isfinite(points).all()
        objects.append((item, points.reshape(-1, 3, 3)))

    triangles = np.concatenate([p for _, p in objects])
    normal = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-20)
    dtype = np.dtype([("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])
    records = np.zeros(len(triangles), dtype=dtype)
    records["n"] = normal
    records["v"] = triangles
    header = b"Pollen Robotics Microduck STAND reference; CC BY-NC-SA 4.0; units mm"
    (ROOT / "microduck-reference-assembly.stl").write_bytes(
        header.ljust(80, b"\0") + struct.pack("<I", len(records)) + records.tobytes()
    )

    gltf = {
        "asset": {"version": "2.0", "generator": "Microduck reference assembler",
                  "copyright": "Pollen Robotics; models CC BY-NC-SA 4.0"},
        "scene": 0, "scenes": [{"nodes": list(range(len(objects)))}],
        "nodes": [], "meshes": [], "materials": [], "accessors": [],
        "bufferViews": [], "buffers": [],
        "extras": {"source": data["source"], "source_commit": data["source_commit"],
                   "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                   "changes": "STAND pose assembled, ground aligned, axes/units converted",
                   "units": "meters", "up_axis": "+Y"},
    }
    binary = bytearray()

    def add_buffer(array, component_type, kind, target, bounds=False):
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(array.tobytes())
        view_id = len(gltf["bufferViews"])
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": offset,
                                     "byteLength": array.nbytes, "target": target})
        accessor = {"bufferView": view_id, "componentType": component_type,
                    "count": len(array), "type": kind}
        if bounds:
            accessor["min"] = array.min(axis=0).tolist()
            accessor["max"] = array.max(axis=0).tolist()
        index = len(gltf["accessors"])
        gltf["accessors"].append(accessor)
        return index

    material_ids = {}
    for index, (item, faces) in enumerate(objects):
        # glTF uses meters and +Y up; STL/source assembly use mm and +Z up.
        vertices = faces.reshape(-1, 3)[:, [0, 2, 1]] / 1000
        vertices[:, 2] *= -1
        vertices, indices = np.unique(vertices.astype("<f4"), axis=0, return_inverse=True)
        indices = indices.astype("<u4")
        positions_id = add_buffer(vertices, 5126, "VEC3", 34962, bounds=True)
        indices_id = add_buffer(indices, 5125, "SCALAR", 34963)
        color = tuple(item["rgba"])
        if color not in material_ids:
            material_ids[color] = len(gltf["materials"])
            gltf["materials"].append({"name": item["mesh"], "doubleSided": True,
                "pbrMetallicRoughness": {"baseColorFactor": list(color),
                                         "metallicFactor": 0.05, "roughnessFactor": 0.65}})
        gltf["nodes"].append({"name": item["name"], "mesh": index})
        gltf["meshes"].append({"name": item["name"], "primitives": [{
            "attributes": {"POSITION": positions_id}, "indices": indices_id,
            "material": material_ids[color], "mode": 4}]})
    while len(binary) % 4:
        binary.append(0)
    gltf["buffers"] = [{"byteLength": len(binary)}]
    metadata = json.dumps(gltf, separators=(",", ":")).encode()
    metadata += b" " * (-len(metadata) % 4)
    length = 12 + 8 + len(metadata) + 8 + len(binary)
    glb = struct.pack("<4sII", b"glTF", 2, length)
    glb += struct.pack("<I4s", len(metadata), b"JSON") + metadata
    glb += struct.pack("<I4s", len(binary), b"BIN\0") + binary
    (ROOT / "microduck-reference-assembly.glb").write_bytes(glb)
    bounds = [triangles.reshape(-1, 3).min(0).tolist(), triangles.reshape(-1, 3).max(0).tolist()]
    report = {"parts": len(objects), "triangles": len(triangles), "bounds_mm": bounds,
              "dimensions_mm": data["dimensions_mm"], "ground_offset_mm": -ground,
              "source": data["source"], "source_commit": data["source_commit"],
              "license": data["license"],
              "note": "Assembly contains separate overlapping meshes, not a single printable manifold."}
    (ROOT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
