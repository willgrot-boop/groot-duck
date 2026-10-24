"""Validate actual CAD exports, including a STEP round trip and mesh topology.

Run from the repository root: python scripts/validate_model.py
The report is written to exports/validation.json. No model files are modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct

import cadquery as cq
import numpy as np


STL_DTYPE = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])


def read_stl(path):
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"Truncated STL: {path}")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise ValueError(f"STL record size mismatch: {path}")
    records = np.frombuffer(data, dtype=STL_DTYPE, count=count, offset=84)
    return records["vertices"].astype(np.float64), records["normal"].astype(np.float64)


def mesh_metrics(vertices, normals, merge_tolerance=1e-5):
    if not np.isfinite(vertices).all() or not np.isfinite(normals).all():
        raise ValueError("Non-finite mesh vertices or normals")
    unique, inverse = np.unique(np.rint(vertices.reshape(-1, 3) / merge_tolerance).astype(np.int64),
                                 axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    collapsed = ((faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) |
                 (faces[:, 2] == faces[:, 0]))
    raw_cross = np.cross(vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0])
    zero_area = np.linalg.norm(raw_cross, axis=1) < merge_tolerance**2
    degenerate = collapsed | zero_area
    usable = faces[~degenerate]
    oriented_edges = np.concatenate((usable[:, [0, 1]], usable[:, [1, 2]], usable[:, [2, 0]]))
    edges, inverse, counts = np.unique(np.sort(oriented_edges, axis=1), axis=0,
                                       return_inverse=True, return_counts=True)
    sign = np.where(oriented_edges[:, 0] < oriented_edges[:, 1], 1, -1)
    orientations = np.bincount(inverse, weights=sign, minlength=len(edges))
    v = vertices[~degenerate]
    signed_volume = np.einsum("ij,ij->i", v[:, 0], np.cross(v[:, 1], v[:, 2])).sum() / 6
    normal_alignment = np.einsum("ij,ij->i", raw_cross, normals)
    return {
        "triangle_count": int(len(vertices)),
        "merged_vertex_count": int(len(unique)),
        "merge_tolerance_mm": merge_tolerance,
        "degenerate_triangle_count": int(degenerate.sum()),
        "boundary_edge_count": int((counts == 1).sum()),
        "nonmanifold_edge_count": int((counts > 2).sum()),
        "inconsistent_edge_winding_count": int((orientations != 0).sum()),
        "reversed_stored_normal_count": int((normal_alignment[~degenerate] < 0).sum()),
        "watertight_after_ignoring_degenerate_triangles": bool(np.all(counts == 2)),
        "positive_oriented_volume": bool(signed_volume > 0),
        "signed_volume_mm3": float(signed_volume),
        "bounds_mm": [vertices.min(axis=(0, 1)).tolist(), vertices.max(axis=(0, 1)).tolist()],
    }


def node_matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T
    x, y, z, w = node.get("rotation", (0, 0, 0, 1))
    rotation = np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ])
    matrix = np.eye(4)
    matrix[:3, :3] = rotation @ np.diag(node.get("scale", (1, 1, 1)))
    matrix[:3, 3] = node.get("translation", (0, 0, 0))
    return matrix


def inspect_glb(path):
    data = path.read_bytes()
    magic, version, total = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError("Invalid GLB header or length")
    chunks = {}
    offset = 12
    while offset < len(data):
        length, kind = struct.unpack_from("<I4s", data, offset)
        chunks[kind] = data[offset + 8:offset + 8 + length]
        offset += 8 + length
    document = json.loads(chunks[b"JSON"])
    binary = chunks[b"BIN\x00"]
    if document["buffers"][0]["byteLength"] > len(binary):
        raise ValueError("Truncated GLB binary buffer")
    component_types = {5120: "<i1", 5121: "<u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
    type_sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

    def accessor(index):
        info = document["accessors"][index]
        view = document["bufferViews"][info["bufferView"]]
        dtype = np.dtype(component_types[info["componentType"]])
        size = type_sizes[info["type"]]
        start = view.get("byteOffset", 0) + info.get("byteOffset", 0)
        stride = view.get("byteStride", dtype.itemsize * size)
        end = start + (info["count"] - 1) * stride + dtype.itemsize * size
        if end > len(binary):
            raise ValueError("GLB accessor extends outside its buffer")
        return np.ndarray((info["count"], size), dtype=dtype, buffer=binary,
                          offset=start, strides=(stride, dtype.itemsize)).copy()

    low, high = np.full(3, np.inf), np.full(3, -np.inf)
    triangles = 0
    mesh_nodes = 0

    def walk(index, parent):
        nonlocal low, high, triangles, mesh_nodes
        node = document["nodes"][index]
        matrix = parent @ node_matrix(node)
        if "mesh" in node:
            mesh_nodes += 1
            for primitive in document["meshes"][node["mesh"]]["primitives"]:
                if primitive.get("mode", 4) != 4:
                    raise ValueError("Non-triangle GLB primitive")
                points = accessor(primitive["attributes"]["POSITION"]).astype(float)
                indices = accessor(primitive["indices"]).ravel()
                if indices.max() >= len(points) or len(indices) % 3:
                    raise ValueError("GLB triangle index out of range")
                if not np.isfinite(points).all():
                    raise ValueError("Non-finite GLB coordinates")
                transformed = points @ matrix[:3, :3].T + matrix[:3, 3]
                low = np.minimum(low, transformed.min(axis=0))
                high = np.maximum(high, transformed.max(axis=0))
                triangles += len(indices) // 3
        for child in node.get("children", []):
            walk(child, matrix)

    for root in document["scenes"][document.get("scene", 0)]["nodes"]:
        walk(root, np.eye(4))
    # glTF's +Y up to the CAD's +Z up; +X remains forward.
    corner1 = np.array([low[0], -high[2], low[1]])
    corner2 = np.array([high[0], -low[2], high[1]])
    meters = bool((corner2 - corner1)[2] < 10)
    unit = 1000 if meters else 1
    return {
        "valid_structure": True,
        "mesh_node_count": mesh_nodes,
        "triangle_count": triangles,
        "standard_meter_units": meters,
        "bounds_mm": [(corner1 * unit).tolist(), (corner2 * unit).tolist()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exports", type=Path, default=Path(__file__).resolve().parents[1] / "exports")
    args = parser.parse_args()
    root = args.exports
    manifest = json.loads((root / "manifest.json").read_text())
    failures = []
    cad = cq.importers.importStep(str(root / "microduck.step")).val()
    solids = cad.Solids()
    bb = cad.BoundingBox()
    cad_bounds = np.array([[bb.xmin, bb.ymin, bb.zmin], [bb.xmax, bb.ymax, bb.zmax]])
    cad_dimensions = cad_bounds[1] - cad_bounds[0]
    expected_dimensions = np.array([manifest["dimensions_mm"][k] for k in ("depth", "width", "height")])
    valid = all(solid.isValid() and solid.Volume() > 0 for solid in solids)
    if not valid or len(solids) != manifest["solid_count"]:
        failures.append("STEP solid count, validity or volume does not match the manifest")
    if not np.allclose(cad_dimensions, expected_dimensions, atol=0.15, rtol=0):
        failures.append("STEP dimensions do not match the manifest")
    step = dict(round_trip_import_passed=True, solid_count=len(solids), all_solids_valid=valid,
                all_solids_positive_volume=all(s.Volume() > 0 for s in solids),
                volume_mm3=cad.Volume(), bounds_mm=cad_bounds.tolist(),
                dimensions_mm=cad_dimensions.tolist())

    records = []
    for part in manifest["parts"]:
        path = root / "parts" / (part["name"] + ".stl")
        vertices, normals = read_stl(path)
        metrics = mesh_metrics(vertices, normals)
        metrics["name"] = part["name"]
        metrics["volume_relative_error_vs_cad"] = abs(metrics["signed_volume_mm3"] - part["volume_mm3"]) / part["volume_mm3"]
        if not metrics["watertight_after_ignoring_degenerate_triangles"]:
            failures.append(f"Non-watertight part STL: {part['name']}")
        if metrics["inconsistent_edge_winding_count"] or not metrics["positive_oriented_volume"]:
            failures.append(f"Incorrect STL winding: {part['name']}")
        if metrics["volume_relative_error_vs_cad"] > 0.03:
            failures.append(f"STL volume differs from CAD by over 3%: {part['name']}")
        records.append(metrics)
    actual_parts = {p.stem for p in (root / "parts").glob("*.stl")}
    if actual_parts != {p["name"] for p in manifest["parts"]}:
        failures.append("Part STL membership differs from manifest")
    vertices, normals = read_stl(root / "microduck.stl")
    stl_bounds = np.array([vertices.min(axis=(0, 1)), vertices.max(axis=(0, 1))])
    if not np.allclose(stl_bounds, cad_bounds, atol=0.15, rtol=0):
        failures.append("Combined STL bounds do not match STEP in millimeters")
    glb = inspect_glb(root / "microduck.glb")
    if not np.allclose(glb["bounds_mm"], stl_bounds, atol=0.15, rtol=0):
        failures.append("GLB world-space bounds do not match STEP/STL")
    if not glb["standard_meter_units"]:
        failures.append("GLB coordinates are millimeters; glTF requires meters")
    if glb["mesh_node_count"] != manifest["part_count"]:
        failures.append("GLB part count differs from manifest")
    files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
             for path in [root / "manifest.json", root / "microduck.step", root / "microduck.stl", root / "microduck.glb"]}
    report = dict(
        checked_at_utc=datetime.now(timezone.utc).isoformat(),
        status="passed" if not failures else "failed", failures=failures,
        source_file_sha256=files, step=step, glb=glb,
        assembled_stl=dict(units="mm", triangles=len(vertices), bounds_mm=stl_bounds.tolist(),
                           interpretation="Separate overlapping closed solids, not a single printable manifold"),
        individual_stl_summary=dict(count=len(records),
            all_watertight_after_ignoring_degenerate_triangles=all(p["watertight_after_ignoring_degenerate_triangles"] for p in records),
            degenerate_triangle_count=sum(p["degenerate_triangle_count"] for p in records),
            all_positive_oriented_volume=all(p["positive_oriented_volume"] for p in records)),
        parts=records,
        limitations="Visual concept only; fit, hardware compatibility, articulation and self-intersections are not validated by these checks.",
    )
    (root / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "failures", "individual_stl_summary")}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
