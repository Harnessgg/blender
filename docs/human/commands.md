# Commands

`harness-blender` is bridge-first. Start the bridge before mutating commands.

## Bridge

```bash
harness-blender bridge start [--host 127.0.0.1] [--port 41749]
harness-blender bridge serve [--host 127.0.0.1] [--port 41749]
harness-blender bridge status
harness-blender bridge stop
harness-blender bridge verify [--iterations 25] [--max-failures 0]
```

## System

```bash
harness-blender actions
harness-blender doctor [--include-render/--no-include-render]
harness-blender version
```

## File

```bash
harness-blender file new <output.blend> [--overwrite]
harness-blender file copy <source.blend> <target.blend> [--overwrite]
harness-blender file inspect <project.blend>
harness-blender file validate <project.blend>
harness-blender file diff <source.blend> <target.blend>
harness-blender file snapshot <project.blend> <description>
harness-blender file undo <project.blend> [--snapshot-id <id>]
harness-blender file redo <project.blend>
```

## Object

```bash
harness-blender object list <project.blend> [--type MESH|CAMERA|LIGHT]
harness-blender object add <project.blend> <CUBE|SPHERE|CYLINDER|PLANE|CONE|TORUS> [--name <name>] [--location-json <json>] [--rotation-json <json>] [--scale-json <json>] [--output <path>]
harness-blender object transform <project.blend> <object_name> [--location-json <json>] [--rotation-json <json>] [--scale-json <json>] [--output <path>]
harness-blender object delete <project.blend> <object_name> [--output <path>]
harness-blender object duplicate <project.blend> <object_name> [--new-name <name>] [--output <path>]
harness-blender object rename <project.blend> <object_name> <new_name> [--output <path>]
harness-blender object parent <project.blend> <child_name> <parent_name> [--output <path>]
harness-blender object unparent <project.blend> <child_name> [--output <path>]
harness-blender object apply-transform <project.blend> <object_name> [--apply-location/--no-apply-location] [--apply-rotation/--no-apply-rotation] [--apply-scale/--no-apply-scale] [--output <path>]
harness-blender object origin-set <project.blend> <object_name> [--origin-type ORIGIN_GEOMETRY|ORIGIN_CURSOR|ORIGIN_CENTER_OF_MASS|ORIGIN_CENTER_OF_VOLUME] [--output <path>]
harness-blender object shade-smooth <project.blend> <object_name> [--output <path>]
harness-blender object shade-flat <project.blend> <object_name> [--output <path>]
```

## Camera

```bash
harness-blender camera add <project.blend> [--name Camera] [--location-json <json>] [--rotation-json <json>] [--output <path>]
harness-blender camera set-active <project.blend> <camera_name> [--output <path>]
harness-blender camera list <project.blend>
harness-blender camera set-lens <project.blend> <camera_name> <lens_mm> [--output <path>]
harness-blender camera set-dof <project.blend> <camera_name> [--use-dof/--no-use-dof] [--focus-distance <float>] [--aperture-fstop <float>] [--focus-object <name>] [--output <path>]
```

## Light

```bash
harness-blender light add <project.blend> <POINT|SUN|SPOT|AREA> [--name <name>] [--energy <float>] [--color <hex>] [--location-json <json>] [--output <path>]
harness-blender light list <project.blend>
harness-blender light set-energy <project.blend> <light_name> <energy> [--output <path>]
harness-blender light set-color <project.blend> <light_name> <hex> [--output <path>]
```

## Material

```bash
harness-blender material list <project.blend>
harness-blender material create <project.blend> <name> [--base-color <hex>] [--metallic <float>] [--roughness <float>] [--output <path>]
harness-blender material assign <project.blend> <object_name> <material_name> [--output <path>]
harness-blender material set-base-color <project.blend> <material_name> <hex> [--output <path>]
harness-blender material set-metallic <project.blend> <material_name> <float> [--output <path>]
harness-blender material set-roughness <project.blend> <material_name> <float> [--output <path>]
```

## Modifier

```bash
harness-blender modifier list <project.blend> <object_name>
harness-blender modifier add <project.blend> <object_name> <modifier_type> [--modifier-name <name>] [--output <path>]
harness-blender modifier remove <project.blend> <object_name> <modifier_name> [--output <path>]
harness-blender modifier apply <project.blend> <object_name> <modifier_name> [--output <path>]
harness-blender geometry-nodes attach <project.blend> <object_name> [--modifier-name <name>] [--output <path>]
harness-blender geometry-nodes set-input <project.blend> <object_name> <input_name> <value_json> [--modifier-name <name>] [--output <path>]
```

## Timeline/Animation

```bash
harness-blender timeline set-frame-range <project.blend> <frame_start> <frame_end> [--output <path>]
harness-blender timeline set-current-frame <project.blend> <frame> [--output <path>]
harness-blender keyframe insert <project.blend> <object_name> <data_path> <frame> [--value <float>] [--array-index <int>] [--output <path>]
harness-blender keyframe delete <project.blend> <object_name> <data_path> <frame> [--array-index <int>] [--output <path>]
harness-blender fcurve list <project.blend> [--object-name <name>]
harness-blender fcurve set-interpolation <project.blend> <object_name> <data_path> <interpolation> [--array-index <int>] [--output <path>]
harness-blender nla track-add <project.blend> <object_name> <track_name> [--output <path>]
harness-blender action list <project.blend>
harness-blender action push-down <project.blend> <object_name> [--output <path>]
harness-blender constraint add <project.blend> <object_name> <constraint_type> [--constraint-name <name>] [--target <object>] [--output <path>]
```

## Import/Export/Assets

```bash
harness-blender import gltf <project.blend> <source> [--output <path>]
harness-blender import fbx <project.blend> <source> [--output <path>]
harness-blender import obj <project.blend> <source> [--output <path>]
harness-blender import usd <project.blend> <source> [--output <path>]
harness-blender export gltf <project.blend> <target>
harness-blender export fbx <project.blend> <target>
harness-blender export obj <project.blend> <target>
harness-blender export usd <project.blend> <target>
harness-blender asset list <project.blend>
harness-blender asset relink-missing <project.blend> <search_dir> [--output <path>]
harness-blender pack resources <project.blend> [--output <path>]
harness-blender unpack resources <project.blend> [--output <path>]
```

## Render

```bash
harness-blender render still <project.blend> <output.png> [--engine BLENDER_EEVEE|CYCLES|BLENDER_WORKBENCH] [--samples <int>] [--resolution-x <int>] [--resolution-y <int>] [--camera <name>]
harness-blender render animation <project.blend> <output_dir> [--engine BLENDER_EEVEE|CYCLES|BLENDER_WORKBENCH] [--frame-start <int>] [--frame-end <int>] [--fps <int>] [--format PNG|JPEG|OPEN_EXR|FFMPEG]
harness-blender render status <job_id>
harness-blender render cancel <job_id>
```
