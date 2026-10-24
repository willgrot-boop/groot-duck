# Official Microduck visual reference

This directory preserves and assembles the official Pollen Robotics Microduck
simulation meshes. It is separate from the editable, simplified CAD model in
`../cad/`. The exact mesh reference is useful for checking the silhouette, pose,
part shapes, and colors; it is not feature-based CAD.

## Files

- `microduck-reference-assembly.glb`: colored, 70-part assembled reference;
  meters, glTF standard +Y up.
- `microduck-reference-assembly.stl`: the same assembly in millimeters, +Z up,
  sitting on Z = 0. The original separate meshes overlap; this is **not** a
  single watertight model ready to print as one piece.
- `microduck-reference-isometric.png`, `microduck-reference-front.png`:
  renderings of the source assembly.
- `assets/*.stl`: 38 unchanged original source meshes, in meters.
- `robot_walk.xml`, `scene_walk.xml`: original upstream MJCF descriptions.
- `assembly.json`: global poses and colors derived from the upstream `STAND`
  keyframe. `transform_mm` maps source vertices **after converting them to
  millimeters** to world millimeters. Exporters then subtract 2.818000472 mm
  from Z to place the feet on the ground.
- `rebuild_reference.py`: self-contained STL/GLB export using the retained
  assets and assembly poses. Requires Python 3 and NumPy; run
  `python reference/rebuild_reference.py` from the repository root.
- `validation.json`: current export counts, bounding box, units and provenance.

The standing reference measures 122.690 mm front-to-back × 142.057 mm across
the legs × 271.616 mm tall. These are the bounds of this particular simulation
assembly and pose, rather than advertised product dimensions. The official
README describes the physical robot as approximately 25 cm tall and 800 g.

The characteristic front has one central circular camera eye with a yellow
surround, a dark recessed face, an arched light head shell, an orange lower
mouth, an exposed articulated neck and legs, and orange feet with yellow soles.

## Attribution and license

**Original 3D models: Copyright Pollen Robotics.** Source:
<https://github.com/pollen-robotics/microduck_rl>, commit
`b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`.

The STL models and their adaptations (assembled STL, GLB and renderings here)
are provided under [Creative Commons Attribution-NonCommercial-ShareAlike 4.0
International](https://creativecommons.org/licenses/by-nc-sa/4.0/).
See the retained upstream `LICENSE-MODELS.md`.

Changes made here: assembled the unchanged source meshes using the upstream
standing joint pose; converted export units and axes; aligned the assembled
feet to the ground; exported a colored GLB, combined STL and reference renders.
These adapted assets retain the same CC BY-NC-SA 4.0 license.

The upstream MJCF files and other upstream code are Apache-2.0, as documented
in the retained upstream `LICENSE`. This distinction matters: the Apache code
license does not replace the model license.

The upstream XML links to the source CAD document:
<https://cad.onshape.com/documents/804927696f06d877f3f1803e/w/5b75db19292e71970de02dee/e/ef6e972847fec8d82570b35e>.
The Onshape document itself was not accessed or exported in this task.

Product reference: <https://pollen-robotics.com/microduck>. This website was
blocked by the execution environment's network proxy; the official public
GitHub sources above supplied the geometry and dimensions.
