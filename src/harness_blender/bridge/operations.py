import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from harness_blender import __version__
from harness_blender.bridge.blender_runner import BlenderRunError, blender_version, run_blender_script


class BridgeOperationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


ACTION_METHODS = [
    "system.health",
    "system.version",
    "system.actions",
    "system.capabilities",
    "system.doctor",
    "project.new",
    "project.copy",
    "project.inspect",
    "project.validate",
    "project.diff",
    "project.snapshot",
    "project.undo",
    "project.redo",
    "scene.object.list",
    "scene.object.add",
    "scene.object.transform",
    "scene.object.delete",
    "scene.object.delete_all",
    "scene.object.material_list",
    "scene.object.duplicate",
    "scene.object.rename",
    "scene.object.parent",
    "scene.object.unparent",
    "scene.object.apply_transform",
    "scene.object.origin_set",
    "scene.object.shade_smooth",
    "scene.object.shade_flat",
    "scene.object.transform_many",
    "scene.object.boolean_union",
    "scene.object.boolean_difference",
    "scene.object.boolean_intersect",
    "scene.object.join",
    "scene.object.convert_mesh",
    "scene.object.shrinkwrap",
    "scene.object.data_transfer",
    "scene.object.group_create",
    "scene.object.parent_many",
    "scene.camera.list",
    "scene.camera.add",
    "scene.camera.set_active",
    "scene.camera.set_lens",
    "scene.camera.set_dof",
    "scene.camera.look_at",
    "scene.camera.rig_product_shot",
    "scene.light.add",
    "scene.light.list",
    "scene.light.set_energy",
    "scene.light.set_color",
    "scene.light.rig_three_point",
    "scene.material.list",
    "scene.material.create",
    "scene.material.assign",
    "scene.material.assign_many",
    "scene.material.set_base_color",
    "scene.material.set_metallic",
    "scene.material.set_roughness",
    "scene.material.set_node_input",
    "scene.modifier.list",
    "scene.modifier.add",
    "scene.modifier.remove",
    "scene.modifier.apply",
    "scene.modifier.set",
    "scene.mesh.smooth",
    "scene.mesh.subdivide",
    "scene.mesh.select_verts",
    "scene.mesh.clear_selection",
    "scene.mesh.transform_selected",
    "scene.mesh.proportional_edit",
    "scene.mesh.extrude_region",
    "scene.mesh.bevel_verts",
    "scene.mesh.merge_by_distance",
    "scene.mesh.loop_cut",
    "scene.mesh.slide_loop",
    "scene.mesh.bisect",
    "scene.mesh.clean",
    "scene.mesh.set_vertex_positions",
    "scene.lattice.add",
    "scene.lattice.bind",
    "scene.lattice.set_point",
    "scene.curve.add_bezier",
    "scene.curve.set_handle",
    "scene.curve.to_mesh",
    "scene.add_reference_image",
    "scene.set_orthographic",
    "scene.world.set_background",
    "scene.color_management.set",
    "analyze.silhouette_diff",
    "scene.geometry_nodes.attach",
    "scene.geometry_nodes.set_input",
    "scene.timeline.set_frame_range",
    "scene.timeline.set_current_frame",
    "scene.keyframe.insert",
    "scene.keyframe.delete",
    "scene.fcurve.list",
    "scene.fcurve.set_interpolation",
    "scene.nla.track_add",
    "scene.action.list",
    "scene.action.push_down",
    "scene.constraint.add",
    "scene.import.gltf",
    "scene.import.fbx",
    "scene.import.obj",
    "scene.import.usd",
    "scene.export.gltf",
    "scene.export.fbx",
    "scene.export.obj",
    "scene.export.usd",
    "scene.asset.list",
    "scene.asset.relink_missing",
    "scene.pack.resources",
    "scene.unpack.resources",
    "render.still",
    "render.animation",
    "render.status",
    "render.cancel",
    "bridge.run_python",
]

RENDER_JOBS: Dict[str, Dict[str, Any]] = {}
RENDER_LOCK = threading.Lock()


SCRIPT_HEADER = """
import json
import os
import traceback

RESULT_PREFIX = "__HARNESS_JSON__"
params = json.loads(os.getenv("HARNESS_PARAMS", "{}"))

def emit(payload):
    print(RESULT_PREFIX + json.dumps(payload, separators=(",", ":"), ensure_ascii=True))

try:
"""

SCRIPT_FOOTER = """
except Exception as exc:
    emit({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})
"""


def _script(body: str) -> str:
    indented = "\n".join(f"    {line}" if line else "" for line in body.strip("\n").splitlines())
    return SCRIPT_HEADER + indented + "\n" + SCRIPT_FOOTER


def _require_file(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise BridgeOperationError("NOT_FOUND", f"File not found: {path}")
    return p


def _target_path(project: str, output: Optional[str]) -> str:
    return str(Path(output) if output else Path(project))


def _run(script: str, *, blend_file: Optional[str], params: Dict[str, Any], timeout: float = 60) -> Dict[str, Any]:
    try:
        out = run_blender_script(script, blend_file=blend_file, params=params, timeout_seconds=timeout)
    except BlenderRunError as exc:
        raise BridgeOperationError(exc.code, exc.message) from exc
    if not out.get("ok", False):
        raise BridgeOperationError("ERROR", out.get("error", "Operation failed"))
    return out


def _system_health(_: Dict[str, Any]) -> Dict[str, Any]:
    try:
        bv = blender_version()
    except BlenderRunError as exc:
        raise BridgeOperationError(exc.code, exc.message) from exc
    return {"ok": True, "blenderVersion": bv}


def _system_version(_: Dict[str, Any]) -> Dict[str, Any]:
    data = {"harnessVersion": __version__}
    try:
        data["blenderVersion"] = blender_version()
    except BlenderRunError:
        data["blenderVersion"] = None
    return data


def _system_actions(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"actions": ACTION_METHODS}


def _system_capabilities(_: Dict[str, Any]) -> Dict[str, Any]:
    return {"actions": ACTION_METHODS, "harnessVersion": __version__}


def _system_doctor(params: Dict[str, Any]) -> Dict[str, Any]:
    include_render = bool(params.get("include_render", True))
    checks = []
    healthy = True
    try:
        checks.append({"name": "blender.binary", "ok": True, "value": blender_version()})
    except BlenderRunError as exc:
        healthy = False
        checks.append({"name": "blender.binary", "ok": False, "error": exc.message})

    if include_render and healthy:
        diag_script = _script(
            """
import bpy
engines = []
for engine in ("BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"):
    try:
        bpy.context.scene.render.engine = engine
        engines.append(engine)
    except Exception:
        pass
cycles_devices = []
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in prefs.devices:
        cycles_devices.append({"name": dev.name, "type": dev.type, "use": bool(dev.use)})
except Exception:
    cycles_devices = []
emit({"ok": True, "engines": engines, "cyclesDevices": cycles_devices, "versionString": bpy.app.version_string})
"""
        )
        try:
            diag = _run(diag_script, blend_file=None, params={}, timeout=30)
            checks.append({"name": "render.capability", "ok": True, "engines": diag.get("engines", [])})
            checks.append({"name": "render.device", "ok": True, "devices": diag.get("cyclesDevices", [])})
        except BridgeOperationError as exc:
            healthy = False
            checks.append({"name": "render.capability", "ok": False, "error": exc.message})

    return {"healthy": healthy, "checks": checks}


def _project_new(params: Dict[str, Any]) -> Dict[str, Any]:
    output = str(Path(params["output"]))
    overwrite = bool(params.get("overwrite", False))
    out_path = Path(output)
    if out_path.exists() and not overwrite:
        raise BridgeOperationError("INVALID_INPUT", f"Target exists: {output}. Use overwrite=true.")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    script = _script(
        """
import bpy
target = params["output"]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=None, params={"output": output}, timeout=60)


def _project_copy(params: Dict[str, Any]) -> Dict[str, Any]:
    source = _require_file(str(params["source"]))
    target = Path(str(params["target"]))
    overwrite = bool(params.get("overwrite", False))
    if target.exists() and not overwrite:
        raise BridgeOperationError("INVALID_INPUT", f"Target exists: {target}. Use overwrite=true.")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {"source": str(source), "target": str(target), "changed": True}


def _project_inspect(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    script = _script(
        """
import bpy
objects = [{
  "name": obj.name,
  "type": obj.type
} for obj in bpy.data.objects]

emit({
  "ok": True,
  "project": bpy.data.filepath,
  "scene": bpy.context.scene.name if bpy.context.scene else None,
  "counts": {
    "objects": len(bpy.data.objects),
    "meshes": len(bpy.data.meshes),
    "materials": len(bpy.data.materials),
    "cameras": len(bpy.data.cameras),
    "lights": len(bpy.data.lights)
  },
  "objects": objects
})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _project_validate(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    script = _script(
        """
import bpy
broken = []
for image in bpy.data.images:
    if image.source == "FILE" and image.filepath:
        abs_path = bpy.path.abspath(image.filepath)
        if not os.path.exists(abs_path):
            broken.append(abs_path)
emit({
  "ok": True,
  "isValid": len(broken) == 0,
  "missingExternalFiles": broken
})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _project_summary(project: str) -> Dict[str, Any]:
    script = _script(
        """
import bpy
objects = [{"name": obj.name, "type": obj.type} for obj in bpy.data.objects]
objects = sorted(objects, key=lambda x: x["name"])
materials = sorted([m.name for m in bpy.data.materials])
emit({
  "ok": True,
  "counts": {
    "objects": len(bpy.data.objects),
    "meshes": len(bpy.data.meshes),
    "materials": len(bpy.data.materials),
    "cameras": len(bpy.data.cameras),
    "lights": len(bpy.data.lights)
  },
  "objects": objects,
  "materials": materials
})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _project_diff(params: Dict[str, Any]) -> Dict[str, Any]:
    source = str(_require_file(str(params["source"])))
    target = str(_require_file(str(params["target"])))
    source_summary = _project_summary(source)
    target_summary = _project_summary(target)

    source_names = {obj["name"] for obj in source_summary["objects"]}
    target_names = {obj["name"] for obj in target_summary["objects"]}
    added_objects = sorted(list(target_names - source_names))
    removed_objects = sorted(list(source_names - target_names))

    source_materials = set(source_summary["materials"])
    target_materials = set(target_summary["materials"])
    added_materials = sorted(list(target_materials - source_materials))
    removed_materials = sorted(list(source_materials - target_materials))

    counts_changed = source_summary["counts"] != target_summary["counts"]
    changed = counts_changed or bool(added_objects or removed_objects or added_materials or removed_materials)
    return {
        "changed": changed,
        "source": source,
        "target": target,
        "counts": {
            "source": source_summary["counts"],
            "target": target_summary["counts"],
        },
        "objects": {
            "added": added_objects,
            "removed": removed_objects,
        },
        "materials": {
            "added": added_materials,
            "removed": removed_materials,
        },
    }


def _snapshot_dir(project_path: Path) -> Path:
    d = project_path.parent / ".harness_blender" / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _snapshot_manifest(project_path: Path) -> Path:
    return _snapshot_dir(project_path) / "manifest.json"


def _snapshot_state(project_path: Path) -> Path:
    return _snapshot_dir(project_path) / "state.json"


def _normalize_path(path: Path) -> str:
    try:
        return str(path.resolve()).lower()
    except Exception:
        return str(path).lower()


def _load_snapshot_entries(project_path: Path) -> list[Dict[str, Any]]:
    manifest_path = _snapshot_manifest(project_path)
    if not manifest_path.exists():
        return []
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        entries = []
    if not isinstance(entries, list):
        return []
    wanted = _normalize_path(project_path)
    filtered: list[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_raw = entry.get("source")
        if not source_raw:
            continue
        source_norm = _normalize_path(Path(str(source_raw)))
        if source_norm == wanted:
            filtered.append(entry)
    return filtered


def _load_snapshot_cursor(project_path: Path, entry_count: int) -> int:
    if entry_count <= 0:
        return -1
    state_path = _snapshot_state(project_path)
    if not state_path.exists():
        return entry_count - 1
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        idx = int(payload.get("currentIndex", entry_count - 1))
        return max(-1, min(idx, entry_count - 1))
    except Exception:
        return entry_count - 1


def _save_snapshot_cursor(project_path: Path, index: int) -> None:
    state_path = _snapshot_state(project_path)
    state_path.write_text(json.dumps({"currentIndex": index}, indent=2), encoding="utf-8")


def _project_snapshot(params: Dict[str, Any]) -> Dict[str, Any]:
    project = _require_file(str(params["project"]))
    description = str(params["description"])
    sid = uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).isoformat()
    snap_dir = _snapshot_dir(project)
    snapshot_file = snap_dir / f"{project.stem}.{sid}.blend"
    shutil.copy2(project, snapshot_file)

    manifest_path = _snapshot_manifest(project)
    entries = []
    if manifest_path.exists():
        try:
            entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    entries.append(
        {
            "id": sid,
            "description": description,
            "source": str(project.resolve()),
            "snapshot": str(snapshot_file.resolve()),
            "createdAt": timestamp,
        }
    )
    manifest_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    scoped_entries = _load_snapshot_entries(project)
    _save_snapshot_cursor(project, len(scoped_entries) - 1)
    return {
        "snapshotId": sid,
        "description": description,
        "snapshot": str(snapshot_file),
        "manifest": str(manifest_path),
        "changed": False,
    }


def _project_undo(params: Dict[str, Any]) -> Dict[str, Any]:
    project = _require_file(str(params["project"]))
    snapshot_id = params.get("snapshot_id")
    entries = _load_snapshot_entries(project)
    if not entries:
        raise BridgeOperationError("NOT_FOUND", "No snapshots found for this project")
    current = _load_snapshot_cursor(project, len(entries))
    if snapshot_id:
        target = next((i for i, e in enumerate(entries) if e.get("id") == snapshot_id), -1)
        if target < 0:
            raise BridgeOperationError("INVALID_INPUT", f"Snapshot not found: {snapshot_id}")
    else:
        target = current - 1
    if target < 0:
        raise BridgeOperationError("INVALID_INPUT", "No earlier snapshot available")
    snap_file = Path(str(entries[target]["snapshot"]))
    if not snap_file.exists():
        raise BridgeOperationError("NOT_FOUND", f"Snapshot file missing: {snap_file}")
    shutil.copy2(snap_file, project)
    _save_snapshot_cursor(project, target)
    return {
        "project": str(project),
        "restoredSnapshotId": entries[target]["id"],
        "description": entries[target].get("description"),
        "changed": True,
    }


def _project_redo(params: Dict[str, Any]) -> Dict[str, Any]:
    project = _require_file(str(params["project"]))
    entries = _load_snapshot_entries(project)
    if not entries:
        raise BridgeOperationError("NOT_FOUND", "No snapshots found for this project")
    current = _load_snapshot_cursor(project, len(entries))
    target = current + 1
    if target >= len(entries):
        raise BridgeOperationError("INVALID_INPUT", "No later snapshot available")
    snap_file = Path(str(entries[target]["snapshot"]))
    if not snap_file.exists():
        raise BridgeOperationError("NOT_FOUND", f"Snapshot file missing: {snap_file}")
    shutil.copy2(snap_file, project)
    _save_snapshot_cursor(project, target)
    return {
        "project": str(project),
        "restoredSnapshotId": entries[target]["id"],
        "description": entries[target].get("description"),
        "changed": True,
    }


def _scene_object_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_type = params.get("type")
    script = _script(
        """
import bpy
wanted = params.get("type")
objects = []
for obj in bpy.data.objects:
    if wanted and obj.type != wanted:
        continue
    objects.append({
      "name": obj.name,
      "type": obj.type,
      "parent": obj.parent.name if obj.parent else None,
      "location": [obj.location.x, obj.location.y, obj.location.z],
      "rotation_euler": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
      "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
    })
emit({"ok": True, "objects": objects})
"""
    )
    return _run(script, blend_file=project, params={"type": object_type}, timeout=60)


def _scene_object_add(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    primitive = str(params["primitive"]).upper()
    primitive_aliases = {
        "UV_SPHERE": "SPHERE",
        "UV-SPHERE": "SPHERE",
        "UVSPHERE": "SPHERE",
    }
    primitive = primitive_aliases.get(primitive, primitive)
    valid_primitives = {"CUBE", "SPHERE", "CYLINDER", "PLANE", "CONE", "TORUS"}
    if primitive not in valid_primitives:
        hint = "Use SPHERE instead of UV_SPHERE." if "SPHERE" in primitive else None
        options = ", ".join(sorted(valid_primitives))
        message = f"Unsupported primitive: {primitive}. Valid primitives: {options}."
        if hint:
            message = f"{message} Hint: {hint}"
        raise BridgeOperationError("INVALID_INPUT", message)
    output = _target_path(project, params.get("output"))
    payload = {
        "primitive": primitive,
        "name": params.get("name"),
        "location": params.get("location", [0.0, 0.0, 0.0]),
        "rotation": params.get("rotation", [0.0, 0.0, 0.0]),
        "scale": params.get("scale", [1.0, 1.0, 1.0]),
        "output": output,
    }
    script = _script(
        """
import bpy
primitive = params["primitive"]
loc = params["location"]
rot = params["rotation"]
scale = params["scale"]
name = params.get("name")
target = params["output"]

if primitive == "CUBE":
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
elif primitive == "SPHERE":
    bpy.ops.mesh.primitive_uv_sphere_add(location=loc, rotation=rot)
elif primitive == "CYLINDER":
    bpy.ops.mesh.primitive_cylinder_add(location=loc, rotation=rot)
elif primitive == "PLANE":
    bpy.ops.mesh.primitive_plane_add(location=loc, rotation=rot)
elif primitive == "CONE":
    bpy.ops.mesh.primitive_cone_add(location=loc, rotation=rot)
elif primitive == "TORUS":
    bpy.ops.mesh.primitive_torus_add(location=loc, rotation=rot)
else:
    raise ValueError(f"Unsupported primitive: {primitive}")

obj = bpy.context.active_object
obj.scale = scale
if name:
    obj.name = name
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": obj.name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_transform(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "location": params.get("location"),
        "rotation": params.get("rotation"),
        "scale": params.get("scale"),
        "output": output,
    }
    script = _script(
        """
import bpy
name = params["object_name"]
obj = bpy.data.objects.get(name)
if not obj:
    raise ValueError(f"Object not found: {name}")
if params.get("location") is not None:
    obj.location = params["location"]
if params.get("rotation") is not None:
    obj.rotation_euler = params["rotation"]
if params.get("scale") is not None:
    obj.scale = params["scale"]
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": obj.name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_delete(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "output": output}
    script = _script(
        """
import bpy
name = params["object_name"]
obj = bpy.data.objects.get(name)
if not obj:
    raise ValueError(f"Object not found: {name}")
bpy.data.objects.remove(obj, do_unlink=True)
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "deleted": name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_delete_all(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {"output": output}
    script = _script(
        """
import bpy
count = len(bpy.data.objects)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "deleted": count, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_material_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
materials = []
for idx, slot in enumerate(obj.material_slots):
    mat = slot.material
    materials.append({
        "index": idx,
        "name": mat.name if mat else None
    })
emit({"ok": True, "object": obj.name, "materials": materials})
"""
    )
    return _run(script, blend_file=project, params={"object_name": object_name}, timeout=60)


def _scene_object_duplicate(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    new_name = params.get("new_name")
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "new_name": new_name,
        "output": output,
    }
    script = _script(
        """
import bpy
name = params["object_name"]
obj = bpy.data.objects.get(name)
if not obj:
    raise ValueError(f"Object not found: {name}")

dup = obj.copy()
if obj.data:
    dup.data = obj.data.copy()
bpy.context.collection.objects.link(dup)

new_name = params.get("new_name")
if new_name:
    dup.name = new_name

target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "sourceObject": name, "object": dup.name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_rename(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    new_name = str(params["new_name"])
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "new_name": new_name,
        "output": output,
    }
    script = _script(
        """
import bpy
old = params["object_name"]
new = params["new_name"]
obj = bpy.data.objects.get(old)
if not obj:
    raise ValueError(f"Object not found: {old}")
if bpy.data.objects.get(new):
    raise ValueError(f"Object already exists: {new}")
obj.name = new
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "oldName": old, "object": new, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_parent(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    child_name = str(params["child_name"])
    parent_name = str(params["parent_name"])
    output = _target_path(project, params.get("output"))
    payload = {"child_name": child_name, "parent_name": parent_name, "output": output}
    script = _script(
        """
import bpy
child = bpy.data.objects.get(params["child_name"])
parent = bpy.data.objects.get(params["parent_name"])
if not child:
    raise ValueError(f"Child object not found: {params['child_name']}")
if not parent:
    raise ValueError(f"Parent object not found: {params['parent_name']}")
if child.name == parent.name:
    raise ValueError("Child and parent must be different objects")
child.parent = parent
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "child": child.name, "parent": parent.name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_unparent(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    child_name = str(params["child_name"])
    output = _target_path(project, params.get("output"))
    payload = {"child_name": child_name, "output": output}
    script = _script(
        """
import bpy
child = bpy.data.objects.get(params["child_name"])
if not child:
    raise ValueError(f"Object not found: {params['child_name']}")
child.parent = None
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "child": child.name, "parent": None, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_apply_transform(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "apply_location": bool(params.get("apply_location", True)),
        "apply_rotation": bool(params.get("apply_rotation", True)),
        "apply_scale": bool(params.get("apply_scale", True)),
        "output": output,
    }
    script = _script(
        """
import bpy
name = params["object_name"]
obj = bpy.data.objects.get(name)
if not obj:
    raise ValueError(f"Object not found: {name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply(
    location=params["apply_location"],
    rotation=params["apply_rotation"],
    scale=params["apply_scale"]
)
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_origin_set(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    origin_type = str(params.get("origin_type", "ORIGIN_GEOMETRY"))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "origin_type": origin_type,
        "output": output,
    }
    script = _script(
        """
import bpy
name = params["object_name"]
obj = bpy.data.objects.get(name)
if not obj:
    raise ValueError(f"Object not found: {name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.origin_set(type=params["origin_type"], center="MEDIAN")
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": name, "originType": params["origin_type"], "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_shade(params: Dict[str, Any], smooth: bool) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "smooth": smooth,
        "output": output,
    }
    script = _script(
        """
import bpy
name = params["object_name"]
obj = bpy.data.objects.get(name)
if not obj:
    raise ValueError(f"Object not found: {name}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {name}")
for poly in obj.data.polygons:
    poly.use_smooth = bool(params["smooth"])
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": name, "smooth": bool(params["smooth"]), "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_object_shade_smooth(params: Dict[str, Any]) -> Dict[str, Any]:
    return _scene_object_shade(params, smooth=True)


def _scene_object_shade_flat(params: Dict[str, Any]) -> Dict[str, Any]:
    return _scene_object_shade(params, smooth=False)


def _scene_object_transform_many(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_names = [str(x) for x in params.get("object_names", [])]
    location = params.get("location")
    rotation = params.get("rotation")
    scale = params.get("scale")
    output = _target_path(project, params.get("output"))
    payload = {
        "object_names": object_names,
        "location": location,
        "rotation": rotation,
        "scale": scale,
        "output": output,
    }
    script = _script(
        """
import bpy
updated = []
for name in params["object_names"]:
    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object not found: {name}")
    if params.get("location") is not None:
        obj.location = params["location"]
    if params.get("rotation") is not None:
        obj.rotation_euler = params["rotation"]
    if params.get("scale") is not None:
        obj.scale = params["scale"]
    updated.append(obj.name)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "updated": updated, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_object_boolean(params: Dict[str, Any], operation: str) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    target_object = str(params["target_object"])
    with_object = str(params["with_object"])
    apply = bool(params.get("apply", True))
    delete_with = bool(params.get("delete_with", True))
    output = _target_path(project, params.get("output"))
    payload = {
        "target_object": target_object,
        "with_object": with_object,
        "operation": operation,
        "apply": apply,
        "delete_with": delete_with,
        "output": output,
    }
    script = _script(
        """
import bpy
target = bpy.data.objects.get(params["target_object"])
other = bpy.data.objects.get(params["with_object"])
if not target:
    raise ValueError(f"Target object not found: {params['target_object']}")
if not other:
    raise ValueError(f"With object not found: {params['with_object']}")
if target.type != "MESH" or other.type != "MESH":
    raise ValueError("Boolean objects must both be mesh objects")
mod = target.modifiers.new(name=f"Bool_{params['operation']}", type="BOOLEAN")
mod.operation = params["operation"]
mod.object = other
if params["apply"]:
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
if params["delete_with"]:
    to_remove = bpy.data.objects.get(params["with_object"])
    if to_remove:
        bpy.data.objects.remove(to_remove, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({
  "ok": True,
  "target": target.name,
  "withObject": params["with_object"],
  "operation": params["operation"],
  "applied": bool(params["apply"]),
  "deletedWithObject": bool(params["delete_with"]),
  "output": params["output"],
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_object_boolean_union(params: Dict[str, Any]) -> Dict[str, Any]:
    return _scene_object_boolean(params, operation="UNION")


def _scene_object_boolean_difference(params: Dict[str, Any]) -> Dict[str, Any]:
    return _scene_object_boolean(params, operation="DIFFERENCE")


def _scene_object_boolean_intersect(params: Dict[str, Any]) -> Dict[str, Any]:
    return _scene_object_boolean(params, operation="INTERSECT")


def _scene_object_join(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_names = params.get("object_names")
    if not isinstance(object_names, list) or len(object_names) < 2:
        raise BridgeOperationError("INVALID_INPUT", "object_names must be a list with at least 2 objects")
    output = _target_path(project, params.get("output"))
    payload = {"object_names": [str(x) for x in object_names], "output": output}
    script = _script(
        """
import bpy
names = params["object_names"]
objs = []
for n in names:
    o = bpy.data.objects.get(n)
    if not o:
        raise ValueError(f"Object not found: {n}")
    objs.append(o)
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "joinedInto": objs[0].name, "joinedCount": len(objs), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_object_convert_mesh(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.convert(target="MESH")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "type": obj.type, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_object_shrinkwrap(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    target_object = str(params["target_object"])
    wrap_method = str(params.get("wrap_method", "NEAREST_SURFACEPOINT")).upper()
    offset = float(params.get("offset", 0.0))
    apply = bool(params.get("apply", True))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "target_object": target_object,
        "wrap_method": wrap_method,
        "offset": offset,
        "apply": apply,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
tgt = bpy.data.objects.get(params["target_object"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if not tgt:
    raise ValueError(f"Target object not found: {params['target_object']}")
if obj.type != "MESH" or tgt.type != "MESH":
    raise ValueError("Shrinkwrap requires mesh objects")
mod = obj.modifiers.new(name="Shrinkwrap", type="SHRINKWRAP")
mod.target = tgt
mod.wrap_method = params["wrap_method"]
mod.offset = float(params["offset"])
if params["apply"]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({
  "ok": True,
  "object": obj.name,
  "target": tgt.name,
  "wrapMethod": mod.wrap_method if not params["apply"] else params["wrap_method"],
  "offset": float(params["offset"]),
  "applied": bool(params["apply"]),
  "output": params["output"],
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_object_data_transfer(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    target_object = str(params["target_object"])
    data_domain = str(params.get("data_domain", "LOOP")).upper()
    data_type = str(params.get("data_type", "CUSTOM_NORMAL")).upper()
    apply = bool(params.get("apply", True))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "target_object": target_object,
        "data_domain": data_domain,
        "data_type": data_type,
        "apply": apply,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
tgt = bpy.data.objects.get(params["target_object"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if not tgt:
    raise ValueError(f"Target object not found: {params['target_object']}")
if obj.type != "MESH" or tgt.type != "MESH":
    raise ValueError("Data transfer requires mesh objects")
mod = obj.modifiers.new(name="DataTransfer", type="DATA_TRANSFER")
mod.object = tgt
domain = params["data_domain"]
dtype = params["data_type"]
if domain == "VERTEX":
    mod.use_vert_data = True
    mod.data_types_verts = {dtype}
elif domain == "EDGE":
    mod.use_edge_data = True
    mod.data_types_edges = {dtype}
elif domain == "POLY":
    mod.use_poly_data = True
    mod.data_types_polys = {dtype}
else:
    mod.use_loop_data = True
    mod.data_types_loops = {dtype}
if params["apply"]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({
  "ok": True,
  "object": obj.name,
  "target": tgt.name,
  "dataDomain": domain,
  "dataType": dtype,
  "applied": bool(params["apply"]),
  "output": params["output"],
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_object_group_create(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    group_name = str(params["group_name"])
    object_names = [str(x) for x in params.get("object_names", [])]
    location = list(params.get("location", [0.0, 0.0, 0.0]))
    output = _target_path(project, params.get("output"))
    payload = {"group_name": group_name, "object_names": object_names, "location": location, "output": output}
    script = _script(
        """
import bpy
empty = bpy.data.objects.new(params["group_name"], None)
empty.empty_display_type = "PLAIN_AXES"
empty.location = tuple(params["location"])
bpy.context.scene.collection.objects.link(empty)
children = []
for name in params["object_names"]:
    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object not found: {name}")
    obj.parent = empty
    children.append(obj.name)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "group": empty.name, "children": children, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_object_parent_many(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    parent_name = str(params["parent_name"])
    child_names = [str(x) for x in params.get("child_names", [])]
    output = _target_path(project, params.get("output"))
    payload = {"parent_name": parent_name, "child_names": child_names, "output": output}
    script = _script(
        """
import bpy
parent = bpy.data.objects.get(params["parent_name"])
if not parent:
    raise ValueError(f"Parent object not found: {params['parent_name']}")
children = []
for name in params["child_names"]:
    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Child object not found: {name}")
    obj.parent = parent
    children.append(obj.name)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "parent": parent.name, "children": children, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_camera_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    script = _script(
        """
import bpy
cams = []
active = bpy.context.scene.camera.name if bpy.context.scene and bpy.context.scene.camera else None
for obj in bpy.data.objects:
    if obj.type != "CAMERA":
        continue
    cam = obj.data
    cams.append({
      "name": obj.name,
      "lens": cam.lens,
      "clip_start": cam.clip_start,
      "clip_end": cam.clip_end,
      "use_dof": cam.dof.use_dof,
      "focus_distance": cam.dof.focus_distance,
      "aperture_fstop": cam.dof.aperture_fstop,
      "isActive": obj.name == active
    })
emit({"ok": True, "cameras": cams})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _scene_camera_add(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    name = str(params.get("name") or "Camera")
    output = _target_path(project, params.get("output"))
    payload = {
        "name": name,
        "location": params.get("location", [0.0, -3.0, 2.0]),
        "rotation": params.get("rotation", [1.1, 0.0, 0.0]),
        "output": output,
    }
    script = _script(
        """
import bpy
bpy.ops.object.camera_add(location=params["location"], rotation=params["rotation"])
obj = bpy.context.active_object
obj.name = params["name"]
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "camera": obj.name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_camera_set_active(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    camera_name = str(params["camera_name"])
    output = _target_path(project, params.get("output"))
    payload = {"camera_name": camera_name, "output": output}
    script = _script(
        """
import bpy
name = params["camera_name"]
obj = bpy.data.objects.get(name)
if not obj or obj.type != "CAMERA":
    raise ValueError(f"Camera not found: {name}")
bpy.context.scene.camera = obj
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "activeCamera": name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_camera_set_lens(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    camera_name = str(params["camera_name"])
    lens = float(params["lens"])
    output = _target_path(project, params.get("output"))
    payload = {"camera_name": camera_name, "lens": lens, "output": output}
    script = _script(
        """
import bpy
name = params["camera_name"]
obj = bpy.data.objects.get(name)
if not obj or obj.type != "CAMERA":
    raise ValueError(f"Camera not found: {name}")
obj.data.lens = float(params["lens"])
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "camera": name, "lens": obj.data.lens, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_camera_set_dof(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    camera_name = str(params["camera_name"])
    output = _target_path(project, params.get("output"))
    payload = {
        "camera_name": camera_name,
        "use_dof": bool(params.get("use_dof", True)),
        "focus_distance": params.get("focus_distance"),
        "aperture_fstop": params.get("aperture_fstop"),
        "focus_object": params.get("focus_object"),
        "output": output,
    }
    script = _script(
        """
import bpy
name = params["camera_name"]
obj = bpy.data.objects.get(name)
if not obj or obj.type != "CAMERA":
    raise ValueError(f"Camera not found: {name}")
dof = obj.data.dof
dof.use_dof = bool(params["use_dof"])
if params.get("focus_distance") is not None:
    dof.focus_distance = float(params["focus_distance"])
if params.get("aperture_fstop") is not None:
    dof.aperture_fstop = float(params["aperture_fstop"])
focus_obj_name = params.get("focus_object")
if focus_obj_name:
    focus_obj = bpy.data.objects.get(focus_obj_name)
    if not focus_obj:
        raise ValueError(f"Focus object not found: {focus_obj_name}")
    dof.focus_object = focus_obj
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({
  "ok": True,
  "camera": name,
  "use_dof": dof.use_dof,
  "focus_distance": dof.focus_distance,
  "aperture_fstop": dof.aperture_fstop,
  "focus_object": dof.focus_object.name if dof.focus_object else None,
  "output": target,
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_camera_look_at(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    camera_name = str(params["camera_name"])
    target_object = params.get("target_object")
    target_location = params.get("target_location")
    output = _target_path(project, params.get("output"))
    payload = {
        "camera_name": camera_name,
        "target_object": str(target_object) if target_object else None,
        "target_location": target_location,
        "output": output,
    }
    script = _script(
        """
import bpy
from mathutils import Vector
cam = bpy.data.objects.get(params["camera_name"])
if not cam or cam.type != "CAMERA":
    raise ValueError(f"Camera not found: {params['camera_name']}")
if params.get("target_object"):
    tgt = bpy.data.objects.get(params["target_object"])
    if not tgt:
        raise ValueError(f"Target object not found: {params['target_object']}")
    target = tgt.matrix_world.translation
else:
    if not params.get("target_location"):
        raise ValueError("Provide target_object or target_location")
    target = Vector(params["target_location"])
direction = (target - cam.matrix_world.translation).normalized()
cam.rotation_mode = "QUATERNION"
cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
cam.rotation_mode = "XYZ"
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "camera": cam.name, "targetObject": params.get("target_object"), "targetLocation": [target.x, target.y, target.z], "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_camera_rig_product_shot(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    camera_name = str(params.get("camera_name") or "ProductCam")
    target_object = str(params["target_object"])
    distance = float(params.get("distance", 4.0))
    height = float(params.get("height", 1.2))
    lens = float(params.get("lens", 60.0))
    output = _target_path(project, params.get("output"))
    payload = {
        "camera_name": camera_name,
        "target_object": target_object,
        "distance": distance,
        "height": height,
        "lens": lens,
        "output": output,
    }
    script = _script(
        """
import bpy
from mathutils import Vector
tgt = bpy.data.objects.get(params["target_object"])
if not tgt:
    raise ValueError(f"Target object not found: {params['target_object']}")
bpy.ops.object.camera_add()
cam = bpy.context.active_object
cam.name = params["camera_name"]
target = tgt.matrix_world.translation
cam.location = Vector((target.x, target.y - float(params["distance"]), target.z + float(params["height"])))
cam.data.lens = float(params["lens"])
direction = (target - cam.matrix_world.translation).normalized()
cam.rotation_mode = "QUATERNION"
cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
cam.rotation_mode = "XYZ"
bpy.context.scene.camera = cam
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "camera": cam.name, "target": tgt.name, "distance": float(params["distance"]), "height": float(params["height"]), "lens": float(params["lens"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _parse_hex_color(color: str) -> list[float]:
    raw = color.strip().lstrip("#")
    if len(raw) not in {6, 8}:
        raise BridgeOperationError("INVALID_INPUT", "Color must be #RRGGBB or #RRGGBBAA")
    try:
        vals = [int(raw[i : i + 2], 16) / 255.0 for i in range(0, len(raw), 2)]
    except ValueError as exc:
        raise BridgeOperationError("INVALID_INPUT", "Invalid hex color") from exc
    if len(vals) == 3:
        vals.append(1.0)
    return vals


def _scene_light_add(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    light_type = str(params.get("light_type", "POINT")).upper()
    output = _target_path(project, params.get("output"))
    color = _parse_hex_color(str(params.get("color", "#FFFFFF")))
    payload = {
        "light_type": light_type,
        "name": str(params.get("name") or "Light"),
        "energy": float(params.get("energy", 1000.0)),
        "location": params.get("location", [0.0, 0.0, 3.0]),
        "color": color,
        "output": output,
    }
    script = _script(
        """
import bpy
bpy.ops.object.light_add(type=params["light_type"], location=params["location"])
obj = bpy.context.active_object
obj.name = params["name"]
obj.data.energy = float(params["energy"])
obj.data.color = params["color"][:3]
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({
  "ok": True,
  "light": obj.name,
  "type": obj.data.type,
  "energy": obj.data.energy,
  "color": [obj.data.color[0], obj.data.color[1], obj.data.color[2]],
  "output": target,
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_light_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    script = _script(
        """
import bpy
lights = []
for obj in bpy.data.objects:
    if obj.type != "LIGHT":
        continue
    data = obj.data
    lights.append({
      "name": obj.name,
      "type": data.type,
      "energy": data.energy,
      "color": [data.color[0], data.color[1], data.color[2]],
      "location": [obj.location.x, obj.location.y, obj.location.z]
    })
emit({"ok": True, "lights": lights})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _scene_light_set_energy(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    light_name = str(params["light_name"])
    energy = float(params["energy"])
    output = _target_path(project, params.get("output"))
    payload = {"light_name": light_name, "energy": energy, "output": output}
    script = _script(
        """
import bpy
name = params["light_name"]
obj = bpy.data.objects.get(name)
if not obj or obj.type != "LIGHT":
    raise ValueError(f"Light not found: {name}")
obj.data.energy = float(params["energy"])
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "light": name, "energy": obj.data.energy, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_light_set_color(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    light_name = str(params["light_name"])
    rgba = _parse_hex_color(str(params["color"]))
    output = _target_path(project, params.get("output"))
    payload = {"light_name": light_name, "color": rgba, "output": output}
    script = _script(
        """
import bpy
name = params["light_name"]
obj = bpy.data.objects.get(name)
if not obj or obj.type != "LIGHT":
    raise ValueError(f"Light not found: {name}")
obj.data.color = params["color"][:3]
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({
  "ok": True,
  "light": name,
  "color": [obj.data.color[0], obj.data.color[1], obj.data.color[2]],
  "output": target,
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_light_rig_three_point(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    target_object = params.get("target_object")
    output = _target_path(project, params.get("output"))
    payload = {"target_object": str(target_object) if target_object else None, "output": output}
    script = _script(
        """
import bpy
from mathutils import Vector
target = Vector((0.0, 0.0, 0.0))
if params.get("target_object"):
    t = bpy.data.objects.get(params["target_object"])
    if not t:
        raise ValueError(f"Target object not found: {params['target_object']}")
    target = t.matrix_world.translation
lights = []
specs = [
    ("KeyLight", (2.5, -2.8, 3.0), 1000.0),
    ("FillLight", (-2.5, -2.2, 1.8), 450.0),
    ("BackLight", (0.0, 2.8, 2.6), 700.0),
]
for name, loc, energy in specs:
    bpy.ops.object.light_add(type="AREA", location=(target.x + loc[0], target.y + loc[1], target.z + loc[2]))
    l = bpy.context.active_object
    l.name = name
    l.data.energy = energy
    direction = (target - l.matrix_world.translation).normalized()
    l.rotation_mode = "QUATERNION"
    l.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    l.rotation_mode = "XYZ"
    lights.append(l.name)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "lights": lights, "targetObject": params.get("target_object"), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_material_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    script = _script(
        """
import bpy
materials = []
for mat in bpy.data.materials:
    entry = {
      "name": mat.name,
      "use_nodes": mat.use_nodes,
      "base_color": list(mat.diffuse_color),
      "metallic": None,
      "roughness": None,
    }
    if mat.use_nodes and mat.node_tree:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            entry["base_color"] = list(bsdf.inputs["Base Color"].default_value)
            entry["metallic"] = bsdf.inputs["Metallic"].default_value
            entry["roughness"] = bsdf.inputs["Roughness"].default_value
    materials.append(entry)
emit({"ok": True, "materials": materials})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _scene_material_create(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    name = str(params["name"])
    output = _target_path(project, params.get("output"))
    base_color = _parse_hex_color(str(params.get("base_color", "#FFFFFF")))
    metallic = float(params.get("metallic", 0.0))
    roughness = float(params.get("roughness", 0.5))
    payload = {
        "name": name,
        "base_color": base_color,
        "metallic": metallic,
        "roughness": roughness,
        "output": output,
    }
    script = _script(
        """
import bpy
name = params["name"]
mat = bpy.data.materials.get(name)
if not mat:
    mat = bpy.data.materials.new(name=name)
mat.use_fake_user = True
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if not bsdf:
    raise ValueError("Principled BSDF node missing")
bsdf.inputs["Base Color"].default_value = params["base_color"]
bsdf.inputs["Metallic"].default_value = float(params["metallic"])
bsdf.inputs["Roughness"].default_value = float(params["roughness"])
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "material": mat.name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_material_assign(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    material_name = str(params["material_name"])
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "material_name": material_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
mat = bpy.data.materials.get(params["material_name"])
if not mat:
    raise ValueError(f"Material not found: {params['material_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
if len(obj.data.materials) == 0:
    obj.data.materials.append(mat)
else:
    obj.data.materials[0] = mat
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": obj.name, "material": mat.name, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_material_assign_many(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_names = [str(x) for x in params.get("object_names", [])]
    material_name = str(params["material_name"])
    output = _target_path(project, params.get("output"))
    payload = {"object_names": object_names, "material_name": material_name, "output": output}
    script = _script(
        """
import bpy
mat = bpy.data.materials.get(params["material_name"])
if not mat:
    raise ValueError(f"Material not found: {params['material_name']}")
updated = []
for name in params["object_names"]:
    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object not found: {name}")
    if obj.type != "MESH":
        raise ValueError(f"Object is not a mesh: {obj.name}")
    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat
    updated.append(obj.name)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "material": mat.name, "updated": updated, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_material_set_value(params: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    material_name = str(params["material_name"])
    output = _target_path(project, params.get("output"))
    payload = {"material_name": material_name, "value": value, "key": key, "output": output}
    script = _script(
        """
import bpy
name = params["material_name"]
mat = bpy.data.materials.get(name)
if not mat:
    raise ValueError(f"Material not found: {name}")
if params["key"] == "base_color":
    rgba = params["value"]
    if mat.use_nodes and mat.node_tree and mat.node_tree.nodes.get("Principled BSDF"):
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba
    else:
        mat.diffuse_color = rgba
elif params["key"] == "metallic":
    if mat.use_nodes and mat.node_tree and mat.node_tree.nodes.get("Principled BSDF"):
        mat.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = float(params["value"])
elif params["key"] == "roughness":
    if mat.use_nodes and mat.node_tree and mat.node_tree.nodes.get("Principled BSDF"):
        mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = float(params["value"])
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "material": name, "key": params["key"], "value": params["value"], "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_material_set_base_color(params: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(params)
    return _scene_material_set_value(p, "base_color", _parse_hex_color(str(params["color"])))


def _scene_material_set_metallic(params: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(params)
    return _scene_material_set_value(p, "metallic", float(params["metallic"]))


def _scene_material_set_roughness(params: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(params)
    return _scene_material_set_value(p, "roughness", float(params["roughness"]))


def _scene_material_set_node_input(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    material_name = str(params["material_name"])
    node_name = str(params["node_name"])
    input_name = str(params["input_name"])
    value = params["value"]
    output = _target_path(project, params.get("output"))
    payload = {
        "material_name": material_name,
        "node_name": node_name,
        "input_name": input_name,
        "value": value,
        "output": output,
    }
    script = _script(
        """
import bpy
mat = bpy.data.materials.get(params["material_name"])
if not mat:
    raise ValueError(f"Material not found: {params['material_name']}")
if not mat.use_nodes or not mat.node_tree:
    raise ValueError("Material does not use nodes")
node = mat.node_tree.nodes.get(params["node_name"])
if not node:
    raise ValueError(f"Node not found: {params['node_name']}")
sock = node.inputs.get(params["input_name"])
if not sock:
    raise ValueError(f"Node input not found: {params['input_name']}")
sock.default_value = params["value"]
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "material": mat.name, "node": node.name, "input": sock.name, "value": params["value"], "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_modifier_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
mods = [{"name": m.name, "type": m.type, "show_viewport": m.show_viewport} for m in obj.modifiers]
emit({"ok": True, "object": obj.name, "modifiers": mods})
"""
    )
    return _run(script, blend_file=project, params={"object_name": object_name}, timeout=60)


def _scene_modifier_add(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    mod_type = str(params["modifier_type"]).upper()
    mod_name = params.get("modifier_name")
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "modifier_type": mod_type, "modifier_name": mod_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
name = params.get("modifier_name") or params["modifier_type"]
mod = obj.modifiers.new(name=name, type=params["modifier_type"])
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": obj.name, "modifier": mod.name, "type": mod.type, "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_modifier_remove(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    modifier_name = str(params["modifier_name"])
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "modifier_name": modifier_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
mod = obj.modifiers.get(params["modifier_name"])
if not mod:
    raise ValueError(f"Modifier not found: {params['modifier_name']}")
obj.modifiers.remove(mod)
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": obj.name, "removed": params["modifier_name"], "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_modifier_apply(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    modifier_name = str(params["modifier_name"])
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "modifier_name": modifier_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if not obj.modifiers.get(params["modifier_name"]):
    raise ValueError(f"Modifier not found: {params['modifier_name']}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier=params["modifier_name"])
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": obj.name, "applied": params["modifier_name"], "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_modifier_set(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    modifier_name = str(params["modifier_name"])
    property_name = str(params["property_name"])
    value = params["value"]
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "modifier_name": modifier_name,
        "property_name": property_name,
        "value": value,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
mod = obj.modifiers.get(params["modifier_name"])
if not mod:
    raise ValueError(f"Modifier not found: {params['modifier_name']}")
prop = params["property_name"]
val = params["value"]
try:
    setattr(mod, prop, val)
except Exception:
    mod[prop] = val
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "modifier": mod.name, "property": prop, "value": val, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_mesh_smooth(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    iterations = int(params.get("iterations", 5))
    factor = float(params.get("factor", 0.5))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "iterations": iterations, "factor": factor, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.vertices_smooth(factor=float(params["factor"]), repeat=int(params["iterations"]))
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "iterations": int(params["iterations"]), "factor": float(params["factor"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_subdivide(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    cuts = int(params.get("cuts", 1))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "cuts": cuts, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.subdivide(number_cuts=int(params["cuts"]))
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "cuts": int(params["cuts"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_select_verts(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    indices = [int(i) for i in params.get("indices", [])]
    replace = bool(params.get("replace", True))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "indices": indices, "replace": replace, "output": output}
    script = _script(
        """
import bpy
import bmesh
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(obj.data)
bm.verts.ensure_lookup_table()
if params["replace"]:
    for v in bm.verts:
        v.select = False
selected = 0
for idx in params["indices"]:
    if 0 <= int(idx) < len(bm.verts):
        bm.verts[int(idx)].select = True
        selected += 1
bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "selected": selected, "replace": bool(params["replace"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_clear_selection(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="DESELECT")
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_transform_selected(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    location = list(params.get("location", [0.0, 0.0, 0.0]))
    rotation = list(params.get("rotation", [0.0, 0.0, 0.0]))
    scale = list(params.get("scale", [1.0, 1.0, 1.0]))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "location": location, "rotation": rotation, "scale": scale, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.transform.translate(value=tuple(params["location"]))
bpy.ops.transform.rotate(value=float(params["rotation"][0]), orient_axis="X")
bpy.ops.transform.rotate(value=float(params["rotation"][1]), orient_axis="Y")
bpy.ops.transform.rotate(value=float(params["rotation"][2]), orient_axis="Z")
bpy.ops.transform.resize(value=tuple(params["scale"]))
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "location": params["location"], "rotation": params["rotation"], "scale": params["scale"], "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_proportional_edit(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    location = list(params.get("location", [0.0, 0.0, 0.0]))
    scale = list(params.get("scale", [1.0, 1.0, 1.0]))
    falloff = str(params.get("falloff", "SMOOTH"))
    radius = float(params.get("radius", 1.0))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "location": location,
        "scale": scale,
        "falloff": falloff,
        "radius": radius,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.transform.translate(
    value=tuple(params["location"]),
    use_proportional_edit=True,
    proportional_edit_falloff=params["falloff"],
    proportional_size=float(params["radius"]),
)
bpy.ops.transform.resize(
    value=tuple(params["scale"]),
    use_proportional_edit=True,
    proportional_edit_falloff=params["falloff"],
    proportional_size=float(params["radius"]),
)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "location": params["location"], "scale": params["scale"], "falloff": params["falloff"], "radius": float(params["radius"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_extrude_region(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    offset = list(params.get("offset", [0.0, 0.0, 0.1]))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "offset": offset, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": tuple(params["offset"])})
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "offset": params["offset"], "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_bevel_verts(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    amount = float(params.get("amount", 0.02))
    segments = int(params.get("segments", 2))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "amount": amount, "segments": segments, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_mode(type="VERT")
bpy.ops.mesh.bevel(offset=float(params["amount"]), segments=int(params["segments"]), affect="VERTICES")
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "amount": float(params["amount"]), "segments": int(params["segments"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_merge_by_distance(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    distance = float(params.get("distance", 0.0001))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "distance": distance, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.remove_doubles(threshold=float(params["distance"]))
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "distance": float(params["distance"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_loop_cut(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    edge_indices = [int(i) for i in params.get("edge_indices", [])]
    cuts = int(params.get("cuts", 1))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "edge_indices": edge_indices, "cuts": cuts, "output": output}
    script = _script(
        """
import bpy
import bmesh
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(obj.data)
bm.edges.ensure_lookup_table()
edges = []
for idx in params["edge_indices"]:
    if 0 <= int(idx) < len(bm.edges):
        edges.append(bm.edges[int(idx)])
if not edges:
    raise ValueError("No valid edge indices provided for loop cut")
bmesh.ops.subdivide_edges(bm, edges=edges, cuts=int(params["cuts"]), use_grid_fill=True)
bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=True)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "edgeCount": len(edges), "cuts": int(params["cuts"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_slide_loop(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    edge_indices = [int(i) for i in params.get("edge_indices", [])]
    factor = float(params.get("factor", 0.0))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "edge_indices": edge_indices, "factor": factor, "output": output}
    script = _script(
        """
import bpy
import bmesh
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_mode(type="EDGE")
bpy.ops.mesh.select_all(action="DESELECT")
bm = bmesh.from_edit_mesh(obj.data)
bm.edges.ensure_lookup_table()
selected_edges = []
for idx in params["edge_indices"]:
    if 0 <= int(idx) < len(bm.edges):
        e = bm.edges[int(idx)]
        e.select = True
        selected_edges.append(e)
if not selected_edges:
    raise ValueError("No valid edge indices provided for slide-loop")
# Background-safe loop slide approximation: move each edge vertex along one connected selected edge.
vert_delta = {}
for e in selected_edges:
    v1, v2 = e.verts[0], e.verts[1]
    if v1.index not in vert_delta:
        vert_delta[v1.index] = (v2.co - v1.co)
    if v2.index not in vert_delta:
        vert_delta[v2.index] = (v1.co - v2.co)
for v in bm.verts:
    d = vert_delta.get(v.index)
    if d is not None:
        v.co = v.co + (d * float(params["factor"]))
bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "edgeCount": len(selected_edges), "factor": float(params["factor"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_bisect(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    plane_co = list(params.get("plane_co", [0.0, 0.0, 0.0]))
    plane_no = list(params.get("plane_no", [0.0, 0.0, 1.0]))
    clear_inner = bool(params.get("clear_inner", False))
    clear_outer = bool(params.get("clear_outer", False))
    use_fill = bool(params.get("use_fill", False))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "plane_co": plane_co,
        "plane_no": plane_no,
        "clear_inner": clear_inner,
        "clear_outer": clear_outer,
        "use_fill": use_fill,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.bisect(
    plane_co=tuple(params["plane_co"]),
    plane_no=tuple(params["plane_no"]),
    clear_inner=bool(params["clear_inner"]),
    clear_outer=bool(params["clear_outer"]),
    use_fill=bool(params["use_fill"]),
)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "planeCo": params["plane_co"], "planeNo": params["plane_no"], "clearInner": bool(params["clear_inner"]), "clearOuter": bool(params["clear_outer"]), "useFill": bool(params["use_fill"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_clean(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    merge_distance = float(params.get("merge_distance", 0.0001))
    dissolve_angle = float(params.get("dissolve_angle", 0.01))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "merge_distance": merge_distance,
        "dissolve_angle": dissolve_angle,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=float(params["merge_distance"]))
bpy.ops.mesh.dissolve_limited(angle_limit=float(params["dissolve_angle"]))
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "mergeDistance": float(params["merge_distance"]), "dissolveAngle": float(params["dissolve_angle"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_mesh_set_vertex_positions(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    positions = params["positions"]  # list of [index, [x, y, z]]
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "positions": positions,
        "output": output,
    }
    script = _script(
        """
import bpy
import bmesh
import json
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if obj.type != "MESH":
    raise ValueError(f"Object is not a mesh: {obj.name}")
positions = params["positions"]
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table()
moved = 0
for entry in positions:
    idx = int(entry[0])
    pos = entry[1]
    if idx < len(bm.verts):
        bm.verts[idx].co.x = float(pos[0])
        bm.verts[idx].co.y = float(pos[1])
        bm.verts[idx].co.z = float(pos[2])
        moved += 1
bm.to_mesh(obj.data)
bm.free()
obj.data.update()
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "moved": moved, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_lattice_add(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    name = str(params.get("name") or "Lattice")
    location = list(params.get("location", [0.0, 0.0, 0.0]))
    scale = list(params.get("scale", [1.0, 1.0, 1.0]))
    points_u = int(params.get("points_u", 2))
    points_v = int(params.get("points_v", 2))
    points_w = int(params.get("points_w", 2))
    output = _target_path(project, params.get("output"))
    payload = {
        "name": name,
        "location": location,
        "scale": scale,
        "points_u": points_u,
        "points_v": points_v,
        "points_w": points_w,
        "output": output,
    }
    script = _script(
        """
import bpy
lat_data = bpy.data.lattices.new(params["name"] + "Data")
lat_data.points_u = int(params["points_u"])
lat_data.points_v = int(params["points_v"])
lat_data.points_w = int(params["points_w"])
lat_obj = bpy.data.objects.new(params["name"], lat_data)
lat_obj.location = tuple(params["location"])
lat_obj.scale = tuple(params["scale"])
bpy.context.scene.collection.objects.link(lat_obj)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({
  "ok": True,
  "lattice": lat_obj.name,
  "points": [lat_data.points_u, lat_data.points_v, lat_data.points_w],
  "output": params["output"],
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_lattice_bind(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    lattice_name = str(params["lattice_name"])
    modifier_name = str(params.get("modifier_name") or "Lattice")
    output = _target_path(project, params.get("output"))
    payload = {"object_name": object_name, "lattice_name": lattice_name, "modifier_name": modifier_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
lat = bpy.data.objects.get(params["lattice_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if not lat or lat.type != "LATTICE":
    raise ValueError(f"Lattice not found: {params['lattice_name']}")
mod = obj.modifiers.new(name=params["modifier_name"], type="LATTICE")
mod.object = lat
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "lattice": lat.name, "modifier": mod.name, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_lattice_set_point(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    lattice_name = str(params["lattice_name"])
    u = int(params["u"])
    v = int(params["v"])
    w = int(params["w"])
    location = list(params.get("location", [0.0, 0.0, 0.0]))
    delta = bool(params.get("delta", False))
    output = _target_path(project, params.get("output"))
    payload = {"lattice_name": lattice_name, "u": u, "v": v, "w": w, "location": location, "delta": delta, "output": output}
    script = _script(
        """
import bpy
lat = bpy.data.objects.get(params["lattice_name"])
if not lat or lat.type != "LATTICE":
    raise ValueError(f"Lattice not found: {params['lattice_name']}")
data = lat.data
u = int(params["u"])
v = int(params["v"])
w = int(params["w"])
if u < 0 or u >= data.points_u or v < 0 or v >= data.points_v or w < 0 or w >= data.points_w:
    raise ValueError("Lattice point indices out of range")
idx = w * (data.points_u * data.points_v) + v * data.points_u + u
pt = data.points[idx]
vec = tuple(params["location"])
if params["delta"]:
    pt.co_deform = (pt.co_deform[0] + vec[0], pt.co_deform[1] + vec[1], pt.co_deform[2] + vec[2])
else:
    pt.co_deform = vec
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({
  "ok": True,
  "lattice": lat.name,
  "index": [u, v, w],
  "coDeform": [pt.co_deform[0], pt.co_deform[1], pt.co_deform[2]],
  "delta": bool(params["delta"]),
  "output": params["output"],
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_curve_add_bezier(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    name = str(params.get("name") or "BezierCurve")
    points = params.get("points") or [[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
    output = _target_path(project, params.get("output"))
    payload = {"name": name, "points": points, "output": output}
    script = _script(
        """
import bpy
pts = params["points"]
if not isinstance(pts, list) or len(pts) < 2:
    raise ValueError("points must include at least 2 entries")
curve_data = bpy.data.curves.new(name=params["name"] + "Data", type="CURVE")
curve_data.dimensions = "3D"
spline = curve_data.splines.new(type="BEZIER")
spline.bezier_points.add(len(pts) - 1)
for i, p in enumerate(pts):
    bp = spline.bezier_points[i]
    bp.co = tuple(p)
    bp.handle_left_type = "AUTO"
    bp.handle_right_type = "AUTO"
obj = bpy.data.objects.new(params["name"], curve_data)
bpy.context.scene.collection.objects.link(obj)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "curve": obj.name, "points": len(pts), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_curve_set_handle(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    curve_name = str(params["curve_name"])
    point_index = int(params["point_index"])
    handle = str(params.get("handle", "left")).lower()
    handle_location = list(params.get("handle_location", [0.0, 0.0, 0.0]))
    handle_type = params.get("handle_type")
    output = _target_path(project, params.get("output"))
    payload = {
        "curve_name": curve_name,
        "point_index": point_index,
        "handle": handle,
        "handle_location": handle_location,
        "handle_type": handle_type,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["curve_name"])
if not obj or obj.type != "CURVE":
    raise ValueError(f"Curve not found: {params['curve_name']}")
if len(obj.data.splines) == 0 or obj.data.splines[0].type != "BEZIER":
    raise ValueError("Curve has no bezier spline")
bp = obj.data.splines[0].bezier_points[int(params["point_index"])]
loc = tuple(params["handle_location"])
if params["handle"] == "right":
    bp.handle_right = loc
    if params.get("handle_type"):
        bp.handle_right_type = str(params["handle_type"]).upper()
else:
    bp.handle_left = loc
    if params.get("handle_type"):
        bp.handle_left_type = str(params["handle_type"]).upper()
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({
  "ok": True,
  "curve": obj.name,
  "pointIndex": int(params["point_index"]),
  "handle": params["handle"],
  "output": params["output"],
  "changed": True
})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_curve_to_mesh(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    curve_name = str(params["curve_name"])
    output = _target_path(project, params.get("output"))
    payload = {"curve_name": curve_name, "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["curve_name"])
if not obj or obj.type != "CURVE":
    raise ValueError(f"Curve not found: {params['curve_name']}")
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.convert(target="MESH")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "type": obj.type, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_add_reference_image(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    image_path = str(_require_file(str(params["image_path"])).resolve())
    name = str(params.get("name") or "ReferenceImage")
    location = list(params.get("location", [0.0, 0.0, 0.0]))
    scale = list(params.get("scale", [1.0, 1.0, 1.0]))
    output = _target_path(project, params.get("output"))
    payload = {"image_path": image_path, "name": name, "location": location, "scale": scale, "output": output}
    script = _script(
        """
import bpy
img = bpy.data.images.load(params["image_path"], check_existing=True)
obj = bpy.data.objects.new(params["name"], None)
obj.empty_display_type = "IMAGE"
obj.data = img
obj.location = tuple(params["location"])
obj.scale = tuple(params["scale"])
bpy.context.scene.collection.objects.link(obj)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "image": img.filepath, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_set_orthographic(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    camera_name = str(params["camera_name"])
    ortho_scale = float(params.get("ortho_scale", 2.0))
    output = _target_path(project, params.get("output"))
    payload = {"camera_name": camera_name, "ortho_scale": ortho_scale, "output": output}
    script = _script(
        """
import bpy
cam_obj = bpy.data.objects.get(params["camera_name"])
if not cam_obj or cam_obj.type != "CAMERA":
    raise ValueError(f"Camera not found: {params['camera_name']}")
cam_obj.data.type = "ORTHO"
cam_obj.data.ortho_scale = float(params["ortho_scale"])
bpy.context.scene.camera = cam_obj
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "camera": cam_obj.name, "type": cam_obj.data.type, "orthoScale": cam_obj.data.ortho_scale, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_world_set_background(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    rgba = _parse_hex_color(str(params["color"]))
    strength = float(params.get("strength", 1.0))
    output = _target_path(project, params.get("output"))
    payload = {"color": rgba, "strength": strength, "output": output}
    script = _script(
        """
import bpy
scene = bpy.context.scene
if scene.world is None:
    scene.world = bpy.data.worlds.new("World")
world = scene.world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes.get("Background")
if not bg:
    bg = nt.nodes.new(type="ShaderNodeBackground")
    out = nt.nodes.get("World Output") or nt.nodes.new(type="ShaderNodeOutputWorld")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
bg.inputs["Color"].default_value = params["color"]
bg.inputs["Strength"].default_value = float(params["strength"])
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "color": params["color"], "strength": float(params["strength"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_color_management_set(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {
        "view_transform": params.get("view_transform"),
        "look": params.get("look"),
        "exposure": params.get("exposure"),
        "gamma": params.get("gamma"),
        "output": output,
    }
    script = _script(
        """
import bpy
vs = bpy.context.scene.view_settings
if params.get("view_transform") is not None:
    vs.view_transform = params["view_transform"]
if params.get("look") is not None:
    vs.look = params["look"]
if params.get("exposure") is not None:
    vs.exposure = float(params["exposure"])
if params.get("gamma") is not None:
    vs.gamma = float(params["gamma"])
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "viewTransform": vs.view_transform, "look": vs.look, "exposure": float(vs.exposure), "gamma": float(vs.gamma), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _analyze_silhouette_diff(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    source_image = str(_require_file(str(params["source_image"])).resolve())
    reference_image = str(_require_file(str(params["reference_image"])).resolve())
    threshold = float(params.get("threshold", 0.1))
    payload = {"source_image": source_image, "reference_image": reference_image, "threshold": threshold}
    script = _script(
        """
import bpy
src = bpy.data.images.load(params["source_image"], check_existing=True)
ref = bpy.data.images.load(params["reference_image"], check_existing=True)
if src.size[0] <= 0 or src.size[1] <= 0 or ref.size[0] <= 0 or ref.size[1] <= 0:
    raise ValueError("Invalid image dimensions")
w = min(int(src.size[0]), int(ref.size[0]))
h = min(int(src.size[1]), int(ref.size[1]))
sp = list(src.pixels)
rp = list(ref.pixels)
def is_on(px, idx, t):
    a = float(px[idx + 3])
    lum = 0.2126 * float(px[idx]) + 0.7152 * float(px[idx + 1]) + 0.0722 * float(px[idx + 2])
    return a > t or lum > t
mismatch = 0
intersection = 0
union = 0
for y in range(h):
    for x in range(w):
        si = (y * int(src.size[0]) + x) * 4
        ri = (y * int(ref.size[0]) + x) * 4
        s_on = is_on(sp, si, float(params["threshold"]))
        r_on = is_on(rp, ri, float(params["threshold"]))
        if s_on != r_on:
            mismatch += 1
        if s_on and r_on:
            intersection += 1
        if s_on or r_on:
            union += 1
total = w * h
diff = (float(mismatch) / float(total)) if total else 1.0
iou = (float(intersection) / float(union)) if union else 0.0
emit({"ok": True, "width": w, "height": h, "difference": diff, "iou": iou, "threshold": float(params["threshold"]), "changed": False})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=120)


def _scene_geometry_nodes_attach(params: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(params)
    p["modifier_type"] = "NODES"
    if "modifier_name" not in p or not p["modifier_name"]:
        p["modifier_name"] = "GeometryNodes"
    return _scene_modifier_add(p)


def _scene_geometry_nodes_set_input(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = str(params["object_name"])
    modifier_name = str(params.get("modifier_name") or "GeometryNodes")
    input_name = str(params["input_name"])
    value = params["value"]
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": object_name,
        "modifier_name": modifier_name,
        "input_name": input_name,
        "value": value,
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
mod = obj.modifiers.get(params["modifier_name"])
if not mod:
    raise ValueError(f"Modifier not found: {params['modifier_name']}")
target_key = None
for k in mod.keys():
    if str(k).lower() == str(params["input_name"]).lower():
        target_key = k
        break
if target_key is None:
    target_key = params["input_name"]
mod[target_key] = params["value"]
target = params["output"]
bpy.ops.wm.save_as_mainfile(filepath=target)
emit({"ok": True, "object": obj.name, "modifier": mod.name, "input": target_key, "value": params["value"], "output": target, "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_timeline_set_frame_range(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    frame_start = int(params["frame_start"])
    frame_end = int(params["frame_end"])
    output = _target_path(project, params.get("output"))
    payload = {"frame_start": frame_start, "frame_end": frame_end, "output": output}
    script = _script(
        """
import bpy
scene = bpy.context.scene
scene.frame_start = int(params["frame_start"])
scene.frame_end = int(params["frame_end"])
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "frameStart": scene.frame_start, "frameEnd": scene.frame_end, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_timeline_set_current_frame(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    frame = int(params["frame"])
    output = _target_path(project, params.get("output"))
    payload = {"frame": frame, "output": output}
    script = _script(
        """
import bpy
scene = bpy.context.scene
scene.frame_set(int(params["frame"]))
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "frame": scene.frame_current, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_keyframe_insert(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": str(params["object_name"]),
        "data_path": str(params["data_path"]),
        "frame": int(params["frame"]),
        "array_index": params.get("array_index"),
        "value": params.get("value"),
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
dp = params["data_path"]
if params.get("value") is not None:
    cur = getattr(obj, dp)
    idx = params.get("array_index")
    if idx is None:
        setattr(obj, dp, params["value"])
    else:
        cur[int(idx)] = params["value"]
obj.keyframe_insert(data_path=dp, frame=int(params["frame"]), index=-1 if params.get("array_index") is None else int(params["array_index"]))
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "dataPath": dp, "frame": int(params["frame"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_keyframe_delete(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": str(params["object_name"]),
        "data_path": str(params["data_path"]),
        "frame": int(params["frame"]),
        "array_index": params.get("array_index"),
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
ok = obj.keyframe_delete(
    data_path=params["data_path"],
    frame=int(params["frame"]),
    index=-1 if params.get("array_index") is None else int(params["array_index"])
)
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "deleted": bool(ok), "object": obj.name, "dataPath": params["data_path"], "frame": int(params["frame"]), "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_fcurve_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    object_name = params.get("object_name")
    payload = {"object_name": object_name}
    script = _script(
        """
import bpy
out = []
if params.get("object_name"):
    obj = bpy.data.objects.get(params["object_name"])
    if not obj:
        raise ValueError(f"Object not found: {params['object_name']}")
    targets = [(obj.name, obj.animation_data.action if obj.animation_data else None)]
else:
    targets = []
    for obj in bpy.data.objects:
        action = obj.animation_data.action if obj.animation_data else None
        if action:
            targets.append((obj.name, action))
for obj_name, action in targets:
    if not action:
        continue
    fcurves = getattr(action, "fcurves", [])
    for fc in fcurves:
        out.append({
          "object": obj_name,
          "action": action.name,
          "data_path": fc.data_path,
          "array_index": fc.array_index,
          "keyframes": len(fc.keyframe_points)
        })
emit({"ok": True, "fcurves": out})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_fcurve_set_interpolation(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": str(params["object_name"]),
        "data_path": str(params["data_path"]),
        "interpolation": str(params["interpolation"]).upper(),
        "array_index": params.get("array_index"),
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if not obj.animation_data or not obj.animation_data.action:
    raise ValueError("Object has no action")
changed = 0
fcurves = getattr(obj.animation_data.action, "fcurves", [])
for fc in fcurves:
    if fc.data_path != params["data_path"]:
        continue
    if params.get("array_index") is not None and fc.array_index != int(params["array_index"]):
        continue
    for kp in fc.keyframe_points:
        kp.interpolation = params["interpolation"]
        changed += 1
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "changedKeyframes": changed, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_nla_track_add(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": str(params["object_name"]), "track_name": str(params["track_name"]), "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if not obj.animation_data:
    obj.animation_data_create()
track = obj.animation_data.nla_tracks.new()
track.name = params["track_name"]
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "track": track.name, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_action_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    script = _script(
        """
import bpy
actions = [{"name": a.name, "fcurves": len(getattr(a, "fcurves", []))} for a in bpy.data.actions]
emit({"ok": True, "actions": actions})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _scene_action_push_down(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {"object_name": str(params["object_name"]), "output": output}
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
if not obj.animation_data or not obj.animation_data.action:
    raise ValueError("Object has no active action")
action_name = obj.animation_data.action.name
track = obj.animation_data.nla_tracks.new()
start = int(bpy.context.scene.frame_start)
track.strips.new(action_name, start, obj.animation_data.action)
obj.animation_data.action = None
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "action": action_name, "track": track.name, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_constraint_add(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {
        "object_name": str(params["object_name"]),
        "constraint_type": str(params["constraint_type"]).upper(),
        "constraint_name": params.get("constraint_name"),
        "target": params.get("target"),
        "output": output,
    }
    script = _script(
        """
import bpy
obj = bpy.data.objects.get(params["object_name"])
if not obj:
    raise ValueError(f"Object not found: {params['object_name']}")
con = obj.constraints.new(type=params["constraint_type"])
if params.get("constraint_name"):
    con.name = params["constraint_name"]
if params.get("target"):
    t = bpy.data.objects.get(params["target"])
    if not t:
        raise ValueError(f"Target object not found: {params['target']}")
    con.target = t
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "object": obj.name, "constraint": con.name, "type": con.type, "target": con.target.name if getattr(con, 'target', None) else None, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=60)


def _scene_import_generic(project: str, operator_name: str, filepath: str, output: str) -> Dict[str, Any]:
    payload = {"filepath": filepath, "operator_name": operator_name, "output": output}
    script = _script(
        """
import bpy
op_name = params["operator_name"]
if op_name == "import_scene.gltf":
    bpy.ops.import_scene.gltf(filepath=params["filepath"])
elif op_name == "import_scene.fbx":
    bpy.ops.import_scene.fbx(filepath=params["filepath"])
elif op_name == "wm.obj_import":
    bpy.ops.wm.obj_import(filepath=params["filepath"])
elif op_name == "wm.usd_import":
    bpy.ops.wm.usd_import(filepath=params["filepath"])
else:
    raise ValueError(f"Unsupported import operator: {op_name}")
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "imported": params["filepath"], "operator": op_name, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=300)


def _scene_export_generic(project: str, operator_name: str, filepath: str) -> Dict[str, Any]:
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    payload = {"filepath": filepath, "operator_name": operator_name}
    script = _script(
        """
import bpy
op_name = params["operator_name"]
if op_name == "export_scene.gltf":
    bpy.ops.export_scene.gltf(filepath=params["filepath"])
elif op_name == "export_scene.fbx":
    bpy.ops.export_scene.fbx(filepath=params["filepath"])
elif op_name == "wm.obj_export":
    bpy.ops.wm.obj_export(filepath=params["filepath"])
elif op_name == "wm.usd_export":
    bpy.ops.wm.usd_export(filepath=params["filepath"])
else:
    raise ValueError(f"Unsupported export operator: {op_name}")
emit({"ok": True, "exported": params["filepath"], "operator": op_name, "changed": False})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=300)


def _scene_import_gltf(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    source = str(_require_file(str(params["source"])))
    output = _target_path(project, params.get("output"))
    return _scene_import_generic(project, "import_scene.gltf", source, output)


def _scene_import_fbx(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    source = str(_require_file(str(params["source"])))
    output = _target_path(project, params.get("output"))
    return _scene_import_generic(project, "import_scene.fbx", source, output)


def _scene_import_obj(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    source = str(_require_file(str(params["source"])))
    output = _target_path(project, params.get("output"))
    return _scene_import_generic(project, "wm.obj_import", source, output)


def _scene_import_usd(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    source = str(_require_file(str(params["source"])))
    output = _target_path(project, params.get("output"))
    return _scene_import_generic(project, "wm.usd_import", source, output)


def _scene_export_gltf(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    return _scene_export_generic(project, "export_scene.gltf", str(Path(params["target"])))


def _scene_export_fbx(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    return _scene_export_generic(project, "export_scene.fbx", str(Path(params["target"])))


def _scene_export_obj(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    return _scene_export_generic(project, "wm.obj_export", str(Path(params["target"])))


def _scene_export_usd(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    return _scene_export_generic(project, "wm.usd_export", str(Path(params["target"])))


def _scene_asset_list(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    script = _script(
        """
import bpy
assets = []
for image in bpy.data.images:
    if image.source == "FILE":
        assets.append({"type": "IMAGE", "name": image.name, "filepath": image.filepath})
for lib in bpy.data.libraries:
    assets.append({"type": "LIBRARY", "name": lib.name, "filepath": lib.filepath})
emit({"ok": True, "assets": assets})
"""
    )
    return _run(script, blend_file=project, params={}, timeout=60)


def _scene_asset_relink_missing(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    search_dir = Path(str(params["search_dir"]))
    if not search_dir.exists():
        raise BridgeOperationError("NOT_FOUND", f"Search directory not found: {search_dir}")
    output = _target_path(project, params.get("output"))
    payload = {"search_dir": str(search_dir), "output": output}
    script = _script(
        """
import bpy
import os
search_dir = params["search_dir"]
relocated = []
for image in bpy.data.images:
    if image.source != "FILE" or not image.filepath:
        continue
    abs_path = bpy.path.abspath(image.filepath)
    if os.path.exists(abs_path):
        continue
    base = os.path.basename(abs_path)
    found = None
    for root, _, files in os.walk(search_dir):
        if base in files:
            found = os.path.join(root, base)
            break
    if found:
        image.filepath = found
        relocated.append({"name": image.name, "filepath": found})
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "relocated": relocated, "output": params["output"], "changed": len(relocated) > 0})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=300)


def _scene_pack_resources(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {"output": output}
    script = _script(
        """
import bpy
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "packed": True, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=300)


def _scene_unpack_resources(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output = _target_path(project, params.get("output"))
    payload = {"output": output}
    script = _script(
        """
import bpy
bpy.ops.file.unpack_all(method='USE_LOCAL')
bpy.ops.wm.save_as_mainfile(filepath=params["output"])
emit({"ok": True, "unpacked": True, "output": params["output"], "changed": True})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=300)


def _render_still(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output_image = str(Path(params["output_image"]))
    engine_raw = str(params.get("engine", "BLENDER_EEVEE")).upper()
    engine_aliases = {
        "EEVEE": "BLENDER_EEVEE",
        "BLENDER_EEVEE_NEXT": "BLENDER_EEVEE",
        "CYCLES": "CYCLES",
        "BLENDER_WORKBENCH": "BLENDER_WORKBENCH",
    }
    engine = engine_aliases.get(engine_raw, engine_raw)
    samples = int(params.get("samples", 64))
    resolution_x = int(params.get("resolution_x", 1920))
    resolution_y = int(params.get("resolution_y", 1080))
    camera = params.get("camera")
    payload = {
        "output_image": output_image,
        "engine": engine,
        "samples": samples,
        "resolution_x": resolution_x,
        "resolution_y": resolution_y,
        "camera": camera,
    }
    script = _script(
        """
import bpy
scene = bpy.context.scene
scene.render.engine = params["engine"]
scene.render.resolution_x = params["resolution_x"]
scene.render.resolution_y = params["resolution_y"]
if scene.render.engine == "CYCLES":
    scene.cycles.samples = params["samples"]

camera_name = params.get("camera")
if camera_name:
    cam = bpy.data.objects.get(camera_name)
    if not cam or cam.type != "CAMERA":
        raise ValueError(f"Camera not found: {camera_name}")
    scene.camera = cam
elif scene.camera is None:
    for obj in bpy.data.objects:
        if obj.type == "CAMERA":
            scene.camera = obj
            break
if scene.camera is None:
    raise ValueError("Cannot render still: no camera in scene")

scene.render.filepath = params["output_image"]
out_path = bpy.path.abspath(params["output_image"])
before_exists = os.path.exists(out_path)
before_mtime = os.path.getmtime(out_path) if before_exists else None
bpy.ops.render.render(write_still=True)
render_result = bpy.data.images.get("Render Result")
if render_result and not os.path.exists(out_path):
    render_result.save_render(filepath=out_path, scene=scene)
if not os.path.exists(out_path):
    raise ValueError(f"Render output missing: {out_path}")
after_mtime = os.path.getmtime(out_path)
changed = (not before_exists) or (before_mtime is not None and after_mtime > before_mtime)
emit({"ok": True, "outputImage": params["output_image"], "changed": bool(changed)})
"""
    )
    return _run(script, blend_file=project, params=payload, timeout=600)


def _render_animation(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(_require_file(str(params["project"])))
    output_dir = str(Path(params["output_dir"]))
    engine_raw = str(params.get("engine", "BLENDER_EEVEE")).upper()
    engine_aliases = {
        "EEVEE": "BLENDER_EEVEE",
        "BLENDER_EEVEE_NEXT": "BLENDER_EEVEE",
        "CYCLES": "CYCLES",
        "BLENDER_WORKBENCH": "BLENDER_WORKBENCH",
    }
    engine = engine_aliases.get(engine_raw, engine_raw)
    frame_start = int(params.get("frame_start", 1))
    frame_end = int(params.get("frame_end", 250))
    fps = int(params.get("fps", 24))
    image_format = str(params.get("format", "PNG")).upper()
    job_id = f"render_{uuid4().hex[:12]}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with RENDER_LOCK:
        RENDER_JOBS[job_id] = {
            "id": job_id,
            "status": "running",
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "type": "animation",
            "project": project,
            "outputDir": output_dir,
            "frameStart": frame_start,
            "frameEnd": frame_end,
        }

    payload = {
        "output_dir": output_dir,
        "engine": engine,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "fps": fps,
        "format": image_format,
    }
    script = _script(
        """
import bpy
scene = bpy.context.scene
scene.render.engine = params["engine"]
scene.frame_start = int(params["frame_start"])
scene.frame_end = int(params["frame_end"])
scene.render.fps = int(params["fps"])
scene.render.image_settings.file_format = params["format"]
if scene.camera is None:
    for obj in bpy.data.objects:
        if obj.type == "CAMERA":
            scene.camera = obj
            break
if scene.camera is None:
    raise ValueError("Cannot render animation: no camera in scene")
scene.render.filepath = params["output_dir"].rstrip("/\\\\") + "/"
bpy.ops.render.render(animation=True)
emit({
  "ok": True,
  "outputDir": params["output_dir"],
  "frameStart": scene.frame_start,
  "frameEnd": scene.frame_end,
  "format": scene.render.image_settings.file_format
})
"""
    )
    try:
        result = _run(script, blend_file=project, params=payload, timeout=1800)
        with RENDER_LOCK:
            RENDER_JOBS[job_id]["status"] = "completed"
            RENDER_JOBS[job_id]["finishedAt"] = datetime.now(timezone.utc).isoformat()
            RENDER_JOBS[job_id]["result"] = result
        return {"jobId": job_id, "status": "completed", "result": result}
    except BridgeOperationError as exc:
        with RENDER_LOCK:
            RENDER_JOBS[job_id]["status"] = "failed"
            RENDER_JOBS[job_id]["finishedAt"] = datetime.now(timezone.utc).isoformat()
            RENDER_JOBS[job_id]["error"] = {"code": exc.code, "message": exc.message}
        raise


def _render_status(params: Dict[str, Any]) -> Dict[str, Any]:
    job_id = str(params["job_id"])
    with RENDER_LOCK:
        job = RENDER_JOBS.get(job_id)
    if not job:
        raise BridgeOperationError("NOT_FOUND", f"Render job not found: {job_id}")
    return dict(job)


def _render_cancel(params: Dict[str, Any]) -> Dict[str, Any]:
    job_id = str(params["job_id"])
    with RENDER_LOCK:
        job = RENDER_JOBS.get(job_id)
        if not job:
            raise BridgeOperationError("NOT_FOUND", f"Render job not found: {job_id}")
        if job.get("status") == "running":
            job["status"] = "cancelled"
            job["finishedAt"] = datetime.now(timezone.utc).isoformat()
            return {"jobId": job_id, "status": "cancelled"}
        return {"jobId": job_id, "status": job.get("status"), "cancelled": False}


def _bridge_run_python(params: Dict[str, Any]) -> Dict[str, Any]:
    project = params.get("project")
    blend_file: Optional[str] = None
    save_path: Optional[str] = None
    if project:
        blend_file = str(_require_file(str(project)))
        save_path = blend_file
    code = str(params["code"])
    user_params = params.get("user_params", {})
    payload = {"code": code, "user_params": user_params, "save_path": save_path}
    script = _script(
        """
import bpy
scope = {"bpy": bpy, "params": params.get("user_params", {})}
exec(params["code"], scope, scope)
if params.get("save_path"):
    bpy.ops.wm.save_as_mainfile(filepath=params["save_path"])
emit({"ok": True, "changed": True})
"""
    )
    return _run(script, blend_file=blend_file, params=payload, timeout=float(params.get("timeout_seconds", 120)))


def execute(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    operations: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
        "system.health": _system_health,
        "system.version": _system_version,
        "system.actions": _system_actions,
        "system.capabilities": _system_capabilities,
        "system.doctor": _system_doctor,
        "project.new": _project_new,
        "project.copy": _project_copy,
        "project.inspect": _project_inspect,
        "project.validate": _project_validate,
        "project.diff": _project_diff,
        "project.snapshot": _project_snapshot,
        "project.undo": _project_undo,
        "project.redo": _project_redo,
        "scene.object.list": _scene_object_list,
        "scene.object.add": _scene_object_add,
        "scene.object.transform": _scene_object_transform,
        "scene.object.delete": _scene_object_delete,
        "scene.object.delete_all": _scene_object_delete_all,
        "scene.object.material_list": _scene_object_material_list,
        "scene.object.duplicate": _scene_object_duplicate,
        "scene.object.rename": _scene_object_rename,
        "scene.object.parent": _scene_object_parent,
        "scene.object.unparent": _scene_object_unparent,
        "scene.object.apply_transform": _scene_object_apply_transform,
        "scene.object.origin_set": _scene_object_origin_set,
        "scene.object.shade_smooth": _scene_object_shade_smooth,
        "scene.object.shade_flat": _scene_object_shade_flat,
        "scene.object.transform_many": _scene_object_transform_many,
        "scene.object.boolean_union": _scene_object_boolean_union,
        "scene.object.boolean_difference": _scene_object_boolean_difference,
        "scene.object.boolean_intersect": _scene_object_boolean_intersect,
        "scene.object.join": _scene_object_join,
        "scene.object.convert_mesh": _scene_object_convert_mesh,
        "scene.object.shrinkwrap": _scene_object_shrinkwrap,
        "scene.object.data_transfer": _scene_object_data_transfer,
        "scene.object.group_create": _scene_object_group_create,
        "scene.object.parent_many": _scene_object_parent_many,
        "scene.camera.list": _scene_camera_list,
        "scene.camera.add": _scene_camera_add,
        "scene.camera.set_active": _scene_camera_set_active,
        "scene.camera.set_lens": _scene_camera_set_lens,
        "scene.camera.set_dof": _scene_camera_set_dof,
        "scene.camera.look_at": _scene_camera_look_at,
        "scene.camera.rig_product_shot": _scene_camera_rig_product_shot,
        "scene.light.add": _scene_light_add,
        "scene.light.list": _scene_light_list,
        "scene.light.set_energy": _scene_light_set_energy,
        "scene.light.set_color": _scene_light_set_color,
        "scene.light.rig_three_point": _scene_light_rig_three_point,
        "scene.material.list": _scene_material_list,
        "scene.material.create": _scene_material_create,
        "scene.material.assign": _scene_material_assign,
        "scene.material.assign_many": _scene_material_assign_many,
        "scene.material.set_base_color": _scene_material_set_base_color,
        "scene.material.set_metallic": _scene_material_set_metallic,
        "scene.material.set_roughness": _scene_material_set_roughness,
        "scene.material.set_node_input": _scene_material_set_node_input,
        "scene.modifier.list": _scene_modifier_list,
        "scene.modifier.add": _scene_modifier_add,
        "scene.modifier.remove": _scene_modifier_remove,
        "scene.modifier.apply": _scene_modifier_apply,
        "scene.modifier.set": _scene_modifier_set,
        "scene.mesh.smooth": _scene_mesh_smooth,
        "scene.mesh.subdivide": _scene_mesh_subdivide,
        "scene.mesh.select_verts": _scene_mesh_select_verts,
        "scene.mesh.clear_selection": _scene_mesh_clear_selection,
        "scene.mesh.transform_selected": _scene_mesh_transform_selected,
        "scene.mesh.proportional_edit": _scene_mesh_proportional_edit,
        "scene.mesh.extrude_region": _scene_mesh_extrude_region,
        "scene.mesh.bevel_verts": _scene_mesh_bevel_verts,
        "scene.mesh.merge_by_distance": _scene_mesh_merge_by_distance,
        "scene.mesh.loop_cut": _scene_mesh_loop_cut,
        "scene.mesh.slide_loop": _scene_mesh_slide_loop,
        "scene.mesh.bisect": _scene_mesh_bisect,
        "scene.mesh.clean": _scene_mesh_clean,
        "scene.mesh.set_vertex_positions": _scene_mesh_set_vertex_positions,
        "scene.lattice.add": _scene_lattice_add,
        "scene.lattice.bind": _scene_lattice_bind,
        "scene.lattice.set_point": _scene_lattice_set_point,
        "scene.curve.add_bezier": _scene_curve_add_bezier,
        "scene.curve.set_handle": _scene_curve_set_handle,
        "scene.curve.to_mesh": _scene_curve_to_mesh,
        "scene.add_reference_image": _scene_add_reference_image,
        "scene.set_orthographic": _scene_set_orthographic,
        "scene.world.set_background": _scene_world_set_background,
        "scene.color_management.set": _scene_color_management_set,
        "analyze.silhouette_diff": _analyze_silhouette_diff,
        "scene.geometry_nodes.attach": _scene_geometry_nodes_attach,
        "scene.geometry_nodes.set_input": _scene_geometry_nodes_set_input,
        "scene.timeline.set_frame_range": _scene_timeline_set_frame_range,
        "scene.timeline.set_current_frame": _scene_timeline_set_current_frame,
        "scene.keyframe.insert": _scene_keyframe_insert,
        "scene.keyframe.delete": _scene_keyframe_delete,
        "scene.fcurve.list": _scene_fcurve_list,
        "scene.fcurve.set_interpolation": _scene_fcurve_set_interpolation,
        "scene.nla.track_add": _scene_nla_track_add,
        "scene.action.list": _scene_action_list,
        "scene.action.push_down": _scene_action_push_down,
        "scene.constraint.add": _scene_constraint_add,
        "scene.import.gltf": _scene_import_gltf,
        "scene.import.fbx": _scene_import_fbx,
        "scene.import.obj": _scene_import_obj,
        "scene.import.usd": _scene_import_usd,
        "scene.export.gltf": _scene_export_gltf,
        "scene.export.fbx": _scene_export_fbx,
        "scene.export.obj": _scene_export_obj,
        "scene.export.usd": _scene_export_usd,
        "scene.asset.list": _scene_asset_list,
        "scene.asset.relink_missing": _scene_asset_relink_missing,
        "scene.pack.resources": _scene_pack_resources,
        "scene.unpack.resources": _scene_unpack_resources,
        "render.still": _render_still,
        "render.animation": _render_animation,
        "render.status": _render_status,
        "render.cancel": _render_cancel,
        "bridge.run_python": _bridge_run_python,
    }
    operation = operations.get(method)
    if operation is None:
        raise BridgeOperationError("INVALID_INPUT", f"Unknown method: {method}")
    try:
        return operation(params)
    except KeyError as exc:
        raise BridgeOperationError("INVALID_INPUT", f"Missing required parameter: {exc}") from exc
