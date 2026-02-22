# Commands

`harnessgg-blender` is bridge-first. Start the bridge before mutating commands.
Guidance for agents: Use CLI commands for interactive exploration and when building something new. Use the Python API for batch operations on known-good workflows.

## Bridge

```bash
harnessgg-blender bridge start [--host 127.0.0.1] [--port 41749]
harnessgg-blender bridge serve [--host 127.0.0.1] [--port 41749]
harnessgg-blender bridge status
harnessgg-blender bridge stop
harnessgg-blender bridge verify [--iterations 25] [--max-failures 0]
harnessgg-blender bridge run-python <script.py> [--project <project.blend>] [--params-json <json>] [--timeout-seconds <int>]
```

## System

```bash
harnessgg-blender actions
harnessgg-blender capabilities
harnessgg-blender doctor [--include-render/--no-include-render]
harnessgg-blender version
harnessgg-blender run-plan <plan.json> [--rollback-on-fail/--no-rollback-on-fail] [--dry-run]
```

`run-plan` schema example:

```json
{
  "project": "tmp/example.blend",
  "variables": { "cube": "MyCube" },
  "steps": [
    { "method": "project.new", "params": { "output": "${project}", "overwrite": true } },
    { "method": "scene.object.add", "params": { "project": "${project}", "primitive": "CUBE", "name": "${cube}", "output": "${project}" } }
  ]
}
```

## File

```bash
harnessgg-blender file new <output.blend> [--overwrite]
harnessgg-blender file copy <source.blend> <target.blend> [--overwrite]
harnessgg-blender file inspect <project.blend>
harnessgg-blender file validate <project.blend>
harnessgg-blender file diff <source.blend> <target.blend>
harnessgg-blender file snapshot <project.blend> <description>
harnessgg-blender file undo <project.blend> [--snapshot-id <id>]
harnessgg-blender file redo <project.blend>
```

## Object

```bash
harnessgg-blender object list <project.blend> [--type MESH|CAMERA|LIGHT]
harnessgg-blender object add <project.blend> <CUBE|SPHERE|CYLINDER|PLANE|CONE|TORUS> [--name <name>] [--location-json <json>] [--rotation-json <json>] [--scale-json <json>] [--output <path>] [--list-primitives]
harnessgg-blender object transform <project.blend> <object_name> [--location-json <json>] [--rotation-json <json>] [--scale-json <json>] [--output <path>]
harnessgg-blender object delete <project.blend> <object_name> [--output <path>]
harnessgg-blender object delete-all <project.blend> [--output <path>]
harnessgg-blender object material-list <project.blend> <object_name>
harnessgg-blender object duplicate <project.blend> <object_name> [--new-name <name>] [--output <path>]
harnessgg-blender object rename <project.blend> <object_name> <new_name> [--output <path>]
harnessgg-blender object parent <project.blend> <child_name> <parent_name> [--output <path>]
harnessgg-blender object unparent <project.blend> <child_name> [--output <path>]
harnessgg-blender object apply-transform <project.blend> <object_name> [--apply-location/--no-apply-location] [--apply-rotation/--no-apply-rotation] [--apply-scale/--no-apply-scale] [--output <path>]
harnessgg-blender object origin-set <project.blend> <object_name> [--origin-type ORIGIN_GEOMETRY|ORIGIN_CURSOR|ORIGIN_CENTER_OF_MASS|ORIGIN_CENTER_OF_VOLUME] [--output <path>]
harnessgg-blender object shade-smooth <project.blend> <object_name> [--output <path>]
harnessgg-blender object shade-flat <project.blend> <object_name> [--output <path>]
harnessgg-blender object transform-many <project.blend> <object_name...> [--location-json <json>] [--rotation-json <json>] [--scale-json <json>] [--output <path>]
harnessgg-blender object boolean-union <project.blend> <target_object> <with_object> [--apply/--no-apply] [--delete-with/--keep-with] [--output <path>]
harnessgg-blender object boolean-difference <project.blend> <target_object> <with_object> [--apply/--no-apply] [--delete-with/--keep-with] [--output <path>]
harnessgg-blender object boolean-intersect <project.blend> <target_object> <with_object> [--apply/--no-apply] [--delete-with/--keep-with] [--output <path>]
harnessgg-blender object join <project.blend> <object_name...> [--output <path>]
harnessgg-blender object convert-mesh <project.blend> <object_name> [--output <path>]
harnessgg-blender object shrinkwrap <project.blend> <object_name> <target_object> [--wrap-method <method>] [--offset <float>] [--apply/--no-apply] [--output <path>]
harnessgg-blender object data-transfer <project.blend> <object_name> <target_object> [--data-domain LOOP|VERTEX|EDGE|POLY] [--data-type <type>] [--apply/--no-apply] [--output <path>]
harnessgg-blender object group-create <project.blend> <group_name> <object_name...> [--location-json <json>] [--output <path>]
harnessgg-blender object parent-many <project.blend> <parent_name> <child_name...> [--output <path>]
```

## Camera

```bash
harnessgg-blender camera add <project.blend> [--name Camera] [--location-json <json>] [--rotation-json <json>] [--output <path>]
harnessgg-blender camera set-active <project.blend> <camera_name> [--output <path>]
harnessgg-blender camera list <project.blend>
harnessgg-blender camera transform <project.blend> <camera_name> [--location-json <json>] [--rotation-json <json>] [--scale-json <json>] [--output <path>]
harnessgg-blender camera set-lens <project.blend> <camera_name> <lens_mm> [--output <path>]
harnessgg-blender camera set-dof <project.blend> <camera_name> [--use-dof/--no-use-dof] [--focus-distance <float>] [--aperture-fstop <float>] [--focus-object <name>] [--output <path>]
harnessgg-blender camera look-at <project.blend> <camera_name> [--target-object <name>] [--target-location-json <json>] [--output <path>]
harnessgg-blender camera rig-product-shot <project.blend> <target_object> [--camera-name <name>] [--distance <float>] [--height <float>] [--lens <float>] [--output <path>]
```

## Light

```bash
harnessgg-blender light add <project.blend> <POINT|SUN|SPOT|AREA> [--name <name>] [--energy <float>] [--color <hex>] [--location-json <json>] [--output <path>]
harnessgg-blender light list <project.blend>
harnessgg-blender light set-energy <project.blend> <light_name> <energy> [--output <path>]
harnessgg-blender light set-color <project.blend> <light_name> <hex> [--output <path>]
harnessgg-blender light rig-three-point <project.blend> [--target-object <name>] [--output <path>]
```

## Material

```bash
harnessgg-blender material list <project.blend>
harnessgg-blender material create <project.blend> <name> [--base-color <hex>] [--metallic <float>] [--roughness <float>] [--output <path>]
harnessgg-blender material assign <project.blend> <object_name> <material_name> [--output <path>]
harnessgg-blender material assign-many <project.blend> <material_name> <object_name...> [--output <path>]
harnessgg-blender material set-base-color <project.blend> <material_name> <hex> [--output <path>]
harnessgg-blender material set-metallic <project.blend> <material_name> <float> [--output <path>]
harnessgg-blender material set-roughness <project.blend> <material_name> <float> [--output <path>]
harnessgg-blender material set-node-input <project.blend> <material_name> <node_name> <input_name> <value_json> [--output <path>]
```

## Modifier

```bash
harnessgg-blender modifier list <project.blend> <object_name>
harnessgg-blender modifier add <project.blend> <object_name> <modifier_type> [--modifier-name <name>] [--output <path>]
harnessgg-blender modifier remove <project.blend> <object_name> <modifier_name> [--output <path>]
harnessgg-blender modifier apply <project.blend> <object_name> <modifier_name> [--output <path>]
harnessgg-blender modifier set <project.blend> <object_name> <modifier_name> <property_name> <value_json> [--output <path>]
harnessgg-blender geometry-nodes attach <project.blend> <object_name> [--modifier-name <name>] [--output <path>]
harnessgg-blender geometry-nodes set-input <project.blend> <object_name> <input_name> <value_json> [--modifier-name <name>] [--output <path>]
```

## Mesh

```bash
harnessgg-blender mesh smooth <project.blend> <object_name> [--iterations <int>] [--factor <float>] [--output <path>]
harnessgg-blender mesh subdivide <project.blend> <object_name> [--cuts <int>] [--output <path>]
harnessgg-blender mesh select-verts <project.blend> <object_name> <indices_json> [--replace/--add] [--output <path>]
harnessgg-blender mesh clear-selection <project.blend> <object_name> [--output <path>]
harnessgg-blender mesh transform-selected <project.blend> <object_name> [--location-json <json>] [--rotation-json <json>] [--scale-json <json>] [--output <path>]
harnessgg-blender mesh proportional-edit <project.blend> <object_name> [--location-json <json>] [--scale-json <json>] [--falloff <mode>] [--radius <float>] [--output <path>]
harnessgg-blender mesh extrude-region <project.blend> <object_name> [--offset-json <json>] [--output <path>]
harnessgg-blender mesh bevel-verts <project.blend> <object_name> [--amount <float>] [--segments <int>] [--output <path>]
harnessgg-blender mesh merge-by-distance <project.blend> <object_name> [--distance <float>] [--output <path>]
harnessgg-blender mesh loop-cut <project.blend> <object_name> <edge_indices_json> [--cuts <int>] [--output <path>]
harnessgg-blender mesh slide-loop <project.blend> <object_name> <edge_indices_json> [--factor <float>] [--output <path>]
harnessgg-blender mesh bisect <project.blend> <object_name> [--plane-co-json <json>] [--plane-no-json <json>] [--clear-inner/--keep-inner] [--clear-outer/--keep-outer] [--use-fill/--no-fill] [--output <path>]
harnessgg-blender mesh clean <project.blend> <object_name> [--merge-distance <float>] [--dissolve-angle <float>] [--output <path>]
```

## Lattice

```bash
harnessgg-blender lattice add <project.blend> [--name Lattice] [--location-json <json>] [--scale-json <json>] [--points-u <int>] [--points-v <int>] [--points-w <int>] [--output <path>]
harnessgg-blender lattice bind <project.blend> <object_name> <lattice_name> [--modifier-name Lattice] [--output <path>]
harnessgg-blender lattice set-point <project.blend> <lattice_name> <u> <v> <w> [--location-json <json>] [--delta/--absolute] [--output <path>]
```

## Curve

```bash
harnessgg-blender curve add-bezier <project.blend> <points_json> [--name BezierCurve] [--output <path>]
harnessgg-blender curve set-handle <project.blend> <curve_name> <point_index> <handle_location_json> [--handle left|right] [--handle-type <type>] [--output <path>]
harnessgg-blender curve to-mesh <project.blend> <curve_name> [--output <path>]
```

## Scene Utilities

```bash
harnessgg-blender scene add-reference-image <project.blend> <image_path> [--name <name>] [--location-json <json>] [--scale-json <json>] [--output <path>]
harnessgg-blender scene set-orthographic <project.blend> <camera_name> [--ortho-scale <float>] [--output <path>]
harnessgg-blender scene set-world-background <project.blend> [--color <hex>] [--strength <float>] [--output <path>]
harnessgg-blender scene set-color-management <project.blend> [--view-transform <name>] [--look <name>] [--exposure <float>] [--gamma <float>] [--output <path>]
```

## Analyze

```bash
harnessgg-blender analyze silhouette-diff <project.blend> <source_image> <reference_image> [--threshold <float>]
```

## Timeline/Animation

```bash
harnessgg-blender timeline set-frame-range <project.blend> <frame_start> <frame_end> [--output <path>]
harnessgg-blender timeline set-current-frame <project.blend> <frame> [--output <path>]
harnessgg-blender keyframe insert <project.blend> <object_name> <data_path> <frame> [--value <float>] [--array-index <int>] [--output <path>]
harnessgg-blender keyframe delete <project.blend> <object_name> <data_path> <frame> [--array-index <int>] [--output <path>]
harnessgg-blender fcurve list <project.blend> [--object-name <name>]
harnessgg-blender fcurve set-interpolation <project.blend> <object_name> <data_path> <interpolation> [--array-index <int>] [--output <path>]
harnessgg-blender nla track-add <project.blend> <object_name> <track_name> [--output <path>]
harnessgg-blender action list <project.blend>
harnessgg-blender action push-down <project.blend> <object_name> [--output <path>]
harnessgg-blender constraint add <project.blend> <object_name> <constraint_type> [--constraint-name <name>] [--target <object>] [--output <path>]
```

## Import/Export/Assets

```bash
harnessgg-blender import gltf <project.blend> <source> [--output <path>]
harnessgg-blender import fbx <project.blend> <source> [--output <path>]
harnessgg-blender import obj <project.blend> <source> [--output <path>]
harnessgg-blender import usd <project.blend> <source> [--output <path>]
harnessgg-blender export gltf <project.blend> <target>
harnessgg-blender export fbx <project.blend> <target>
harnessgg-blender export obj <project.blend> <target>
harnessgg-blender export usd <project.blend> <target>
harnessgg-blender asset list <project.blend>
harnessgg-blender asset relink-missing <project.blend> <search_dir> [--output <path>]
harnessgg-blender pack resources <project.blend> [--output <path>]
harnessgg-blender unpack resources <project.blend> [--output <path>]
```

## Render

```bash
harnessgg-blender render still <project.blend> <output.png> [--engine BLENDER_EEVEE|CYCLES|BLENDER_WORKBENCH] [--samples <int>] [--resolution-x <int>] [--resolution-y <int>] [--camera <name>]
harnessgg-blender render animation <project.blend> <output_dir> [--engine BLENDER_EEVEE|CYCLES|BLENDER_WORKBENCH] [--frame-start <int>] [--frame-end <int>] [--fps <int>] [--format PNG|JPEG|OPEN_EXR|FFMPEG]
harnessgg-blender render status <job_id>
harnessgg-blender render cancel <job_id>
```
