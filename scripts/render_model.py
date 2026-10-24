"""Render the exported CAD assembly in Blender, without additional Python packages.

Run from the repository root:
    blender --background --python scripts/render_model.py -- --views all

The model remains untouched; ground, cameras and lighting exist only in the
presentation .blend file. Inputs use +X forward, +Y left, +Z up in millimetres.
"""

import argparse
from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector


def parse_arguments():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=root / "exports/microduck.glb")
    parser.add_argument("--output", type=Path, default=root / "exports")
    parser.add_argument("--views", choices=["all", "iso", "front", "side", "ortho"], default="all")
    parser.add_argument("--samples", type=int, default=80)
    parser.add_argument("--denoise", action="store_true",
                        help="Enable only on Blender builds with OpenImageDenoise support")
    parser.add_argument("--resolution", type=int, default=1500)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def bounds(objects):
    points = [obj.matrix_world @ Vector(corner)
              for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    if not points:
        raise RuntimeError("The GLB contains no mesh geometry")
    return (Vector([min(p[i] for p in points) for i in range(3)]),
            Vector([max(p[i] for p in points) for i in range(3)]))


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area_light(name, location, energy, size, target, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    return obj


def main():
    args = parse_arguments()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(args.input.resolve()))
    imported = list(bpy.context.scene.objects)
    root = bpy.data.objects.new("CAD presentation transform", None)
    bpy.context.collection.objects.link(root)
    for obj in imported:
        if obj.parent is None:
            world = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_world = world
    bpy.context.view_layer.update()
    low, high = bounds(imported)
    extent = high - low
    tallest_axis = max(range(3), key=lambda i: extent[i])
    # Blender's glTF importer normally restores Z-up. Accept raw Y-up exports too.
    if tallest_axis == 1:
        root.rotation_euler.x = math.pi / 2
    elif tallest_axis == 0:
        root.rotation_euler.y = -math.pi / 2
    bpy.context.view_layer.update()
    low, high = bounds(imported)
    unit_scale = 0.001 if high.z - low.z > 10 else 1.0
    root.scale = (unit_scale,) * 3
    bpy.context.view_layer.update()
    low, high = bounds(imported)
    root.location = (-(low.x + high.x) / 2, -(low.y + high.y) / 2, -low.z)
    bpy.context.view_layer.update()
    low, high = bounds(imported)
    extent = high - low
    height = extent.z
    center = (low + high) / 2
    print("PRESENTATION_BOUNDS_METERS", tuple(low), tuple(high), flush=True)

    for material in bpy.data.materials:
        if not material.use_nodes:
            continue
        shader = material.node_tree.nodes.get("Principled BSDF")
        if shader:
            shader.inputs["Roughness"].default_value = 0.36
            shader.inputs["Metallic"].default_value = 0.04
    # Preserve CAD normals and the crisp machined edges in the source geometry.

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    # The cloud Blender build lacks OpenImageDenoise; samples remain deterministic
    # and denoising is opt-in for other installations.
    scene.cycles.use_denoising = args.denoise
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 6
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.world.use_nodes = True
    world = scene.world.node_tree.nodes.get("Background")
    world.inputs["Color"].default_value = (0.79, 0.84, 0.91, 1)
    world.inputs["Strength"].default_value = 0.35

    bpy.ops.mesh.primitive_plane_add(size=height * 200, location=(0, 0, -0.0004))
    floor = bpy.context.object
    floor.name = "Studio floor (presentation only)"
    material = bpy.data.materials.new("Warm white studio")
    material.diffuse_color = (0.86, 0.85, 0.82, 1)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.86, 0.85, 0.82, 1)
    shader.inputs["Roughness"].default_value = 0.72
    floor.data.materials.append(material)
    target = Vector((0, 0, height * 0.52))
    area_light("Large softbox", (height * 1.1, -height * 1.6, height * 2.5),
               9 * (height / 0.27) ** 2, height * 1.8, target, (1.0, 0.94, 0.86))
    area_light("Cool fill", (height * 0.5, height * 1.7, height * 1.4),
               4 * (height / 0.27) ** 2, height * 1.8, target, (0.84, 0.91, 1.0))
    area_light("Rim softbox", (-height * 1.5, height * 0.3, height * 2.1),
               7 * (height / 0.27) ** 2, height * 1.5, target)

    camera_data = bpy.data.cameras.new("Presentation camera")
    camera = bpy.data.objects.new("Presentation camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.lens = 55
    camera_data.clip_start = 0.001
    camera_data.clip_end = 100
    scene.camera = camera

    views = {
        "iso": ((2.5, -3.2, 1.9), "microduck_preview.png", 1.3),
        "front": ((4.0, 0, 0), "microduck_front.png", 1.20),
        "side": ((0, -4.0, 0), "microduck_side.png", 1.20),
    }
    selected_views = list(views) if args.views == "all" else (
        ["front", "side"] if args.views == "ortho" else [args.views])
    for view in selected_views:
        direction, filename, scale = views[view]
        camera.location = target + Vector(direction) * height
        aim(camera, target)
        camera_data.ortho_scale = height * scale
        scene.render.filepath = str((args.output / filename).resolve())
        print("RENDERING", view, scene.render.filepath, flush=True)
        if view == "iso":
            bpy.ops.wm.save_as_mainfile(filepath=str((args.output / "microduck_studio.blend").resolve()))
        bpy.ops.render.render(write_still=True)
    print("RENDER_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
