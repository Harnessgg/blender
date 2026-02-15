# Command Spec (LLM)

Global rules:
1. Commands print one JSON object to stdout.
2. Bridge-backed commands fail with `BRIDGE_UNAVAILABLE` if bridge is down.
3. Start bridge with `harness-blender bridge start`.

Exit codes:
- `0` success
- `1` internal error
- `2` not found
- `3` validation failed
- `4` invalid input
- `5` bridge unavailable

Implemented RPC methods:
- `system.health`
- `system.version`
- `system.actions`
- `system.doctor`
- `project.new`
- `project.copy`
- `project.inspect`
- `project.validate`
- `project.diff`
- `project.snapshot`
- `project.undo`
- `project.redo`
- `scene.object.list`
- `scene.object.add`
- `scene.object.transform`
- `scene.object.delete`
- `scene.object.duplicate`
- `scene.object.rename`
- `scene.object.parent`
- `scene.object.unparent`
- `scene.object.apply_transform`
- `scene.object.origin_set`
- `scene.object.shade_smooth`
- `scene.object.shade_flat`
- `scene.camera.list`
- `scene.camera.add`
- `scene.camera.set_active`
- `scene.camera.set_lens`
- `scene.camera.set_dof`
- `scene.light.add`
- `scene.light.list`
- `scene.light.set_energy`
- `scene.light.set_color`
- `scene.material.list`
- `scene.material.create`
- `scene.material.assign`
- `scene.material.set_base_color`
- `scene.material.set_metallic`
- `scene.material.set_roughness`
- `scene.modifier.list`
- `scene.modifier.add`
- `scene.modifier.remove`
- `scene.modifier.apply`
- `scene.geometry_nodes.attach`
- `scene.geometry_nodes.set_input`
- `scene.timeline.set_frame_range`
- `scene.timeline.set_current_frame`
- `scene.keyframe.insert`
- `scene.keyframe.delete`
- `scene.fcurve.list`
- `scene.fcurve.set_interpolation`
- `scene.nla.track_add`
- `scene.action.list`
- `scene.action.push_down`
- `scene.constraint.add`
- `scene.import.gltf`
- `scene.import.fbx`
- `scene.import.obj`
- `scene.import.usd`
- `scene.export.gltf`
- `scene.export.fbx`
- `scene.export.obj`
- `scene.export.usd`
- `scene.asset.list`
- `scene.asset.relink_missing`
- `scene.pack.resources`
- `scene.unpack.resources`
- `render.still`
- `render.animation`
- `render.status`
- `render.cancel`
