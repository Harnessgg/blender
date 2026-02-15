import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import typer

from harness_blender import __version__
from harness_blender.bridge.client import BridgeClient, BridgeClientError
from harness_blender.bridge.protocol import ERROR_CODES, PROTOCOL_VERSION
from harness_blender.bridge.server import run_bridge_server

app = typer.Typer(add_completion=False, help="Bridge-first CLI for Blender automation")
bridge_app = typer.Typer(add_completion=False, help="Bridge lifecycle")
file_app = typer.Typer(add_completion=False, help="File/project commands")
object_app = typer.Typer(add_completion=False, help="Object commands")
camera_app = typer.Typer(add_completion=False, help="Camera commands")
light_app = typer.Typer(add_completion=False, help="Light commands")
material_app = typer.Typer(add_completion=False, help="Material commands")
modifier_app = typer.Typer(add_completion=False, help="Modifier commands")
geometry_nodes_app = typer.Typer(add_completion=False, help="Geometry nodes commands")
timeline_app = typer.Typer(add_completion=False, help="Timeline commands")
keyframe_app = typer.Typer(add_completion=False, help="Keyframe commands")
fcurve_app = typer.Typer(add_completion=False, help="F-Curve commands")
nla_app = typer.Typer(add_completion=False, help="NLA commands")
action_app = typer.Typer(add_completion=False, help="Action commands")
constraint_app = typer.Typer(add_completion=False, help="Constraint commands")
import_app = typer.Typer(add_completion=False, help="Import commands")
export_app = typer.Typer(add_completion=False, help="Export commands")
asset_app = typer.Typer(add_completion=False, help="Asset commands")
pack_app = typer.Typer(add_completion=False, help="Pack commands")
unpack_app = typer.Typer(add_completion=False, help="Unpack commands")
render_app = typer.Typer(add_completion=False, help="Render commands")

app.add_typer(bridge_app, name="bridge")
app.add_typer(file_app, name="file")
app.add_typer(object_app, name="object")
app.add_typer(camera_app, name="camera")
app.add_typer(light_app, name="light")
app.add_typer(material_app, name="material")
app.add_typer(modifier_app, name="modifier")
app.add_typer(geometry_nodes_app, name="geometry-nodes")
app.add_typer(timeline_app, name="timeline")
app.add_typer(keyframe_app, name="keyframe")
app.add_typer(fcurve_app, name="fcurve")
app.add_typer(nla_app, name="nla")
app.add_typer(action_app, name="action")
app.add_typer(constraint_app, name="constraint")
app.add_typer(import_app, name="import")
app.add_typer(export_app, name="export")
app.add_typer(asset_app, name="asset")
app.add_typer(pack_app, name="pack")
app.add_typer(unpack_app, name="unpack")
app.add_typer(render_app, name="render")


def _print(payload: Dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _ok(command: str, data: Dict[str, Any]) -> None:
    if isinstance(data, dict):
        if "changed" in data and "idempotent" not in data:
            data["idempotent"] = False
        data.setdefault("warnings", [])
    _print({"ok": True, "protocolVersion": PROTOCOL_VERSION, "command": command, "data": data})


def _fail(command: str, code: str, message: str, retryable: bool = False) -> None:
    _print(
        {
            "ok": False,
            "protocolVersion": PROTOCOL_VERSION,
            "command": command,
            "error": {"code": code, "message": message, "retryable": retryable},
        }
    )
    raise SystemExit(ERROR_CODES.get(code, ERROR_CODES["ERROR"]))


def _bridge_client() -> BridgeClient:
    from_env = os.getenv("HARNESS_BLENDER_BRIDGE_URL")
    if from_env:
        return BridgeClient(from_env)
    url_file = _bridge_url_file()
    if url_file.exists():
        return BridgeClient(url_file.read_text(encoding="utf-8").strip())
    return BridgeClient("http://127.0.0.1:41749")


def _call_bridge(command: str, method: str, params: Dict[str, Any], timeout_seconds: float = 30) -> Dict[str, Any]:
    client = _bridge_client()
    try:
        return client.call(method, params, timeout_seconds=timeout_seconds)
    except BridgeClientError as exc:
        _fail(command, exc.code, exc.message, retryable=exc.code == "BRIDGE_UNAVAILABLE")
    except Exception as exc:
        _fail(command, "ERROR", str(exc))
    raise RuntimeError("unreachable")


def _ensure_bridge_ready(command: str) -> None:
    _call_bridge(command, "system.health", {}, timeout_seconds=20)


def _bridge_state_dir() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", Path.home()))
    state_dir = root / "harness-blender"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _bridge_pid_file() -> Path:
    return _bridge_state_dir() / "bridge.pid"


def _bridge_url_file() -> Path:
    return _bridge_state_dir() / "bridge.url"


@bridge_app.command("serve")
def bridge_serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(41749, "--port"),
) -> None:
    run_bridge_server(host, port)


@bridge_app.command("start")
def bridge_start(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(41749, "--port"),
) -> None:
    pid_file = _bridge_pid_file()
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            _ok("bridge.start", {"status": "already-running", "pid": pid, "host": host, "port": port})
            return
        except Exception:
            pid_file.unlink(missing_ok=True)

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    process = subprocess.Popen(
        [sys.executable, "-m", "harness_blender", "bridge", "serve", "--host", host, "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    pid_file.write_text(str(process.pid), encoding="utf-8")
    url = f"http://{host}:{port}"
    os.environ["HARNESS_BLENDER_BRIDGE_URL"] = url
    _bridge_url_file().write_text(url, encoding="utf-8")
    for _ in range(30):
        time.sleep(0.1)
        try:
            health = BridgeClient(f"http://{host}:{port}").health()
            if health.get("ok"):
                _ok("bridge.start", {"status": "started", "pid": process.pid, "host": host, "port": port})
                return
        except BridgeClientError:
            continue
    _fail("bridge.start", "BRIDGE_UNAVAILABLE", "Bridge process started but health check failed")


@bridge_app.command("stop")
def bridge_stop() -> None:
    pid_file = _bridge_pid_file()
    if not pid_file.exists():
        _ok("bridge.stop", {"status": "not-running"})
        return
    pid = int(pid_file.read_text(encoding="utf-8").strip())
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    pid_file.unlink(missing_ok=True)
    _bridge_url_file().unlink(missing_ok=True)
    _ok("bridge.stop", {"status": "stopped", "pid": pid})


@bridge_app.command("status")
def bridge_status() -> None:
    client = _bridge_client()
    try:
        health = client.health()
        _ok("bridge.status", {"running": True, "health": health, "url": client.url})
    except BridgeClientError as exc:
        _fail("bridge.status", exc.code, exc.message, retryable=True)


@bridge_app.command("verify")
def bridge_verify(
    iterations: int = typer.Option(25, "--iterations", min=1, max=500),
    max_failures: int = typer.Option(0, "--max-failures", min=0),
) -> None:
    failures = 0
    latencies_ms = []
    client = _bridge_client()
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            client.call("system.health", {})
        except BridgeClientError:
            failures += 1
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(round(elapsed_ms, 3))
        time.sleep(0.02)
    stable = failures <= max_failures
    data = {
        "stable": stable,
        "iterations": iterations,
        "failures": failures,
        "maxFailuresAllowed": max_failures,
        "latencyMs": {
            "min": min(latencies_ms),
            "max": max(latencies_ms),
            "avg": round(sum(latencies_ms) / len(latencies_ms), 3),
        },
    }
    _ok("bridge.verify", data)
    if not stable:
        raise SystemExit(ERROR_CODES["ERROR"])


@app.command("actions")
def actions() -> None:
    _ok("actions", _call_bridge("actions", "system.actions", {}))


@app.command("doctor")
def doctor(include_render: bool = True) -> None:
    _ensure_bridge_ready("doctor")
    data = _call_bridge("doctor", "system.doctor", {"include_render": include_render}, timeout_seconds=60)
    _ok("doctor", data)
    if not data.get("healthy", False):
        raise SystemExit(ERROR_CODES["ERROR"])


@app.command("version")
def version() -> None:
    _ok("version", {"harnessVersion": __version__})


@file_app.command("new")
def file_new(
    output: Path,
    overwrite: bool = False,
) -> None:
    _ensure_bridge_ready("file.new")
    _ok("file.new", _call_bridge("file.new", "project.new", {"output": str(output), "overwrite": overwrite}))


@file_app.command("copy")
def file_copy(
    source: Path,
    target: Path,
    overwrite: bool = False,
) -> None:
    _ensure_bridge_ready("file.copy")
    _ok(
        "file.copy",
        _call_bridge(
            "file.copy",
            "project.copy",
            {"source": str(source), "target": str(target), "overwrite": overwrite},
        ),
    )


@file_app.command("inspect")
def file_inspect(project: Path) -> None:
    _ok("file.inspect", _call_bridge("file.inspect", "project.inspect", {"project": str(project)}, timeout_seconds=60))


@file_app.command("validate")
def file_validate(project: Path) -> None:
    data = _call_bridge("file.validate", "project.validate", {"project": str(project)}, timeout_seconds=60)
    _ok("file.validate", data)
    if not data.get("isValid", False):
        raise SystemExit(ERROR_CODES["VALIDATION_FAILED"])


@file_app.command("diff")
def file_diff(source: Path, target: Path) -> None:
    _ok(
        "file.diff",
        _call_bridge(
            "file.diff",
            "project.diff",
            {"source": str(source), "target": str(target)},
            timeout_seconds=120,
        ),
    )


@file_app.command("snapshot")
def file_snapshot(project: Path, description: str) -> None:
    _ensure_bridge_ready("file.snapshot")
    _ok(
        "file.snapshot",
        _call_bridge(
            "file.snapshot",
            "project.snapshot",
            {"project": str(project), "description": description},
            timeout_seconds=30,
        ),
    )


@file_app.command("undo")
def file_undo(project: Path, snapshot_id: Optional[str] = typer.Option(None, "--snapshot-id")) -> None:
    _ensure_bridge_ready("file.undo")
    _ok(
        "file.undo",
        _call_bridge(
            "file.undo",
            "project.undo",
            {"project": str(project), "snapshot_id": snapshot_id},
            timeout_seconds=30,
        ),
    )


@file_app.command("redo")
def file_redo(project: Path) -> None:
    _ensure_bridge_ready("file.redo")
    _ok(
        "file.redo",
        _call_bridge(
            "file.redo",
            "project.redo",
            {"project": str(project)},
            timeout_seconds=30,
        ),
    )


@object_app.command("list")
def object_list(project: Path, type: Optional[str] = typer.Option(None, "--type")) -> None:
    _ok(
        "object.list",
        _call_bridge(
            "object.list",
            "scene.object.list",
            {"project": str(project), "type": type.upper() if type else None},
            timeout_seconds=60,
        ),
    )


@object_app.command("add")
def object_add(
    project: Path,
    primitive: str,
    name: Optional[str] = typer.Option(None, "--name"),
    location_json: str = typer.Option("[0,0,0]", "--location-json"),
    rotation_json: str = typer.Option("[0,0,0]", "--rotation-json"),
    scale_json: str = typer.Option("[1,1,1]", "--scale-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.add")
    _ok(
        "object.add",
        _call_bridge(
            "object.add",
            "scene.object.add",
            {
                "project": str(project),
                "primitive": primitive,
                "name": name,
                "location": json.loads(location_json),
                "rotation": json.loads(rotation_json),
                "scale": json.loads(scale_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("transform")
def object_transform(
    project: Path,
    object_name: str,
    location_json: Optional[str] = typer.Option(None, "--location-json"),
    rotation_json: Optional[str] = typer.Option(None, "--rotation-json"),
    scale_json: Optional[str] = typer.Option(None, "--scale-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.transform")
    _ok(
        "object.transform",
        _call_bridge(
            "object.transform",
            "scene.object.transform",
            {
                "project": str(project),
                "object_name": object_name,
                "location": json.loads(location_json) if location_json else None,
                "rotation": json.loads(rotation_json) if rotation_json else None,
                "scale": json.loads(scale_json) if scale_json else None,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("delete")
def object_delete(project: Path, object_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("object.delete")
    _ok(
        "object.delete",
        _call_bridge(
            "object.delete",
            "scene.object.delete",
            {"project": str(project), "object_name": object_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@object_app.command("duplicate")
def object_duplicate(
    project: Path,
    object_name: str,
    new_name: Optional[str] = typer.Option(None, "--new-name"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.duplicate")
    _ok(
        "object.duplicate",
        _call_bridge(
            "object.duplicate",
            "scene.object.duplicate",
            {
                "project": str(project),
                "object_name": object_name,
                "new_name": new_name,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("rename")
def object_rename(
    project: Path,
    object_name: str,
    new_name: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.rename")
    _ok(
        "object.rename",
        _call_bridge(
            "object.rename",
            "scene.object.rename",
            {
                "project": str(project),
                "object_name": object_name,
                "new_name": new_name,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("parent")
def object_parent(
    project: Path,
    child_name: str,
    parent_name: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.parent")
    _ok(
        "object.parent",
        _call_bridge(
            "object.parent",
            "scene.object.parent",
            {
                "project": str(project),
                "child_name": child_name,
                "parent_name": parent_name,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("unparent")
def object_unparent(
    project: Path,
    child_name: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.unparent")
    _ok(
        "object.unparent",
        _call_bridge(
            "object.unparent",
            "scene.object.unparent",
            {
                "project": str(project),
                "child_name": child_name,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("apply-transform")
def object_apply_transform(
    project: Path,
    object_name: str,
    apply_location: bool = typer.Option(True, "--apply-location/--no-apply-location"),
    apply_rotation: bool = typer.Option(True, "--apply-rotation/--no-apply-rotation"),
    apply_scale: bool = typer.Option(True, "--apply-scale/--no-apply-scale"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.apply-transform")
    _ok(
        "object.apply-transform",
        _call_bridge(
            "object.apply-transform",
            "scene.object.apply_transform",
            {
                "project": str(project),
                "object_name": object_name,
                "apply_location": apply_location,
                "apply_rotation": apply_rotation,
                "apply_scale": apply_scale,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("origin-set")
def object_origin_set(
    project: Path,
    object_name: str,
    origin_type: str = typer.Option("ORIGIN_GEOMETRY", "--origin-type"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.origin-set")
    _ok(
        "object.origin-set",
        _call_bridge(
            "object.origin-set",
            "scene.object.origin_set",
            {
                "project": str(project),
                "object_name": object_name,
                "origin_type": origin_type,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@object_app.command("shade-smooth")
def object_shade_smooth(project: Path, object_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("object.shade-smooth")
    _ok(
        "object.shade-smooth",
        _call_bridge(
            "object.shade-smooth",
            "scene.object.shade_smooth",
            {"project": str(project), "object_name": object_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@object_app.command("shade-flat")
def object_shade_flat(project: Path, object_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("object.shade-flat")
    _ok(
        "object.shade-flat",
        _call_bridge(
            "object.shade-flat",
            "scene.object.shade_flat",
            {"project": str(project), "object_name": object_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@camera_app.command("list")
def camera_list(project: Path) -> None:
    _ok("camera.list", _call_bridge("camera.list", "scene.camera.list", {"project": str(project)}, timeout_seconds=60))


@camera_app.command("add")
def camera_add(
    project: Path,
    name: str = typer.Option("Camera", "--name"),
    location_json: str = typer.Option("[0,-3,2]", "--location-json"),
    rotation_json: str = typer.Option("[1.1,0,0]", "--rotation-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("camera.add")
    _ok(
        "camera.add",
        _call_bridge(
            "camera.add",
            "scene.camera.add",
            {
                "project": str(project),
                "name": name,
                "location": json.loads(location_json),
                "rotation": json.loads(rotation_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@camera_app.command("set-active")
def camera_set_active(project: Path, camera_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("camera.set-active")
    _ok(
        "camera.set-active",
        _call_bridge(
            "camera.set-active",
            "scene.camera.set_active",
            {"project": str(project), "camera_name": camera_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@camera_app.command("set-lens")
def camera_set_lens(
    project: Path,
    camera_name: str,
    lens: float,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("camera.set-lens")
    _ok(
        "camera.set-lens",
        _call_bridge(
            "camera.set-lens",
            "scene.camera.set_lens",
            {"project": str(project), "camera_name": camera_name, "lens": lens, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@camera_app.command("set-dof")
def camera_set_dof(
    project: Path,
    camera_name: str,
    use_dof: bool = typer.Option(True, "--use-dof/--no-use-dof"),
    focus_distance: Optional[float] = typer.Option(None, "--focus-distance"),
    aperture_fstop: Optional[float] = typer.Option(None, "--aperture-fstop"),
    focus_object: Optional[str] = typer.Option(None, "--focus-object"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("camera.set-dof")
    _ok(
        "camera.set-dof",
        _call_bridge(
            "camera.set-dof",
            "scene.camera.set_dof",
            {
                "project": str(project),
                "camera_name": camera_name,
                "use_dof": use_dof,
                "focus_distance": focus_distance,
                "aperture_fstop": aperture_fstop,
                "focus_object": focus_object,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@light_app.command("add")
def light_add(
    project: Path,
    light_type: str,
    name: Optional[str] = typer.Option(None, "--name"),
    energy: float = typer.Option(1000.0, "--energy"),
    color: str = typer.Option("#FFFFFF", "--color"),
    location_json: str = typer.Option("[0,0,3]", "--location-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("light.add")
    _ok(
        "light.add",
        _call_bridge(
            "light.add",
            "scene.light.add",
            {
                "project": str(project),
                "light_type": light_type,
                "name": name,
                "energy": energy,
                "color": color,
                "location": json.loads(location_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@light_app.command("list")
def light_list(project: Path) -> None:
    _ok("light.list", _call_bridge("light.list", "scene.light.list", {"project": str(project)}, timeout_seconds=60))


@light_app.command("set-energy")
def light_set_energy(
    project: Path,
    light_name: str,
    energy: float,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("light.set-energy")
    _ok(
        "light.set-energy",
        _call_bridge(
            "light.set-energy",
            "scene.light.set_energy",
            {"project": str(project), "light_name": light_name, "energy": energy, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@light_app.command("set-color")
def light_set_color(
    project: Path,
    light_name: str,
    color: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("light.set-color")
    _ok(
        "light.set-color",
        _call_bridge(
            "light.set-color",
            "scene.light.set_color",
            {"project": str(project), "light_name": light_name, "color": color, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@material_app.command("list")
def material_list(project: Path) -> None:
    _ok("material.list", _call_bridge("material.list", "scene.material.list", {"project": str(project)}, timeout_seconds=60))


@material_app.command("create")
def material_create(
    project: Path,
    name: str,
    base_color: str = typer.Option("#FFFFFF", "--base-color"),
    metallic: float = typer.Option(0.0, "--metallic"),
    roughness: float = typer.Option(0.5, "--roughness"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("material.create")
    _ok(
        "material.create",
        _call_bridge(
            "material.create",
            "scene.material.create",
            {
                "project": str(project),
                "name": name,
                "base_color": base_color,
                "metallic": metallic,
                "roughness": roughness,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@material_app.command("assign")
def material_assign(
    project: Path,
    object_name: str,
    material_name: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("material.assign")
    _ok(
        "material.assign",
        _call_bridge(
            "material.assign",
            "scene.material.assign",
            {"project": str(project), "object_name": object_name, "material_name": material_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@material_app.command("set-base-color")
def material_set_base_color(
    project: Path,
    material_name: str,
    color: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("material.set-base-color")
    _ok(
        "material.set-base-color",
        _call_bridge(
            "material.set-base-color",
            "scene.material.set_base_color",
            {"project": str(project), "material_name": material_name, "color": color, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@material_app.command("set-metallic")
def material_set_metallic(
    project: Path,
    material_name: str,
    metallic: float,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("material.set-metallic")
    _ok(
        "material.set-metallic",
        _call_bridge(
            "material.set-metallic",
            "scene.material.set_metallic",
            {"project": str(project), "material_name": material_name, "metallic": metallic, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@material_app.command("set-roughness")
def material_set_roughness(
    project: Path,
    material_name: str,
    roughness: float,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("material.set-roughness")
    _ok(
        "material.set-roughness",
        _call_bridge(
            "material.set-roughness",
            "scene.material.set_roughness",
            {"project": str(project), "material_name": material_name, "roughness": roughness, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@modifier_app.command("list")
def modifier_list(project: Path, object_name: str) -> None:
    _ok(
        "modifier.list",
        _call_bridge("modifier.list", "scene.modifier.list", {"project": str(project), "object_name": object_name}, timeout_seconds=60),
    )


@modifier_app.command("add")
def modifier_add(
    project: Path,
    object_name: str,
    modifier_type: str,
    modifier_name: Optional[str] = typer.Option(None, "--modifier-name"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("modifier.add")
    _ok(
        "modifier.add",
        _call_bridge(
            "modifier.add",
            "scene.modifier.add",
            {
                "project": str(project),
                "object_name": object_name,
                "modifier_type": modifier_type,
                "modifier_name": modifier_name,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@modifier_app.command("remove")
def modifier_remove(
    project: Path,
    object_name: str,
    modifier_name: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("modifier.remove")
    _ok(
        "modifier.remove",
        _call_bridge(
            "modifier.remove",
            "scene.modifier.remove",
            {"project": str(project), "object_name": object_name, "modifier_name": modifier_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@modifier_app.command("apply")
def modifier_apply(
    project: Path,
    object_name: str,
    modifier_name: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("modifier.apply")
    _ok(
        "modifier.apply",
        _call_bridge(
            "modifier.apply",
            "scene.modifier.apply",
            {"project": str(project), "object_name": object_name, "modifier_name": modifier_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@geometry_nodes_app.command("attach")
def geometry_nodes_attach(
    project: Path,
    object_name: str,
    modifier_name: str = typer.Option("GeometryNodes", "--modifier-name"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("geometry-nodes.attach")
    _ok(
        "geometry-nodes.attach",
        _call_bridge(
            "geometry-nodes.attach",
            "scene.geometry_nodes.attach",
            {"project": str(project), "object_name": object_name, "modifier_name": modifier_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@geometry_nodes_app.command("set-input")
def geometry_nodes_set_input(
    project: Path,
    object_name: str,
    input_name: str,
    value_json: str,
    modifier_name: str = typer.Option("GeometryNodes", "--modifier-name"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("geometry-nodes.set-input")
    _ok(
        "geometry-nodes.set-input",
        _call_bridge(
            "geometry-nodes.set-input",
            "scene.geometry_nodes.set_input",
            {
                "project": str(project),
                "object_name": object_name,
                "modifier_name": modifier_name,
                "input_name": input_name,
                "value": json.loads(value_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@timeline_app.command("set-frame-range")
def timeline_set_frame_range(project: Path, frame_start: int, frame_end: int, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("timeline.set-frame-range")
    _ok(
        "timeline.set-frame-range",
        _call_bridge(
            "timeline.set-frame-range",
            "scene.timeline.set_frame_range",
            {"project": str(project), "frame_start": frame_start, "frame_end": frame_end, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@timeline_app.command("set-current-frame")
def timeline_set_current_frame(project: Path, frame: int, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("timeline.set-current-frame")
    _ok(
        "timeline.set-current-frame",
        _call_bridge(
            "timeline.set-current-frame",
            "scene.timeline.set_current_frame",
            {"project": str(project), "frame": frame, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@keyframe_app.command("insert")
def keyframe_insert(
    project: Path,
    object_name: str,
    data_path: str,
    frame: int,
    value: Optional[float] = typer.Option(None, "--value"),
    array_index: Optional[int] = typer.Option(None, "--array-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("keyframe.insert")
    _ok(
        "keyframe.insert",
        _call_bridge(
            "keyframe.insert",
            "scene.keyframe.insert",
            {
                "project": str(project),
                "object_name": object_name,
                "data_path": data_path,
                "frame": frame,
                "value": value,
                "array_index": array_index,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@keyframe_app.command("delete")
def keyframe_delete(
    project: Path,
    object_name: str,
    data_path: str,
    frame: int,
    array_index: Optional[int] = typer.Option(None, "--array-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("keyframe.delete")
    _ok(
        "keyframe.delete",
        _call_bridge(
            "keyframe.delete",
            "scene.keyframe.delete",
            {
                "project": str(project),
                "object_name": object_name,
                "data_path": data_path,
                "frame": frame,
                "array_index": array_index,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@fcurve_app.command("list")
def fcurve_list(project: Path, object_name: Optional[str] = typer.Option(None, "--object-name")) -> None:
    _ok(
        "fcurve.list",
        _call_bridge("fcurve.list", "scene.fcurve.list", {"project": str(project), "object_name": object_name}, timeout_seconds=60),
    )


@fcurve_app.command("set-interpolation")
def fcurve_set_interpolation(
    project: Path,
    object_name: str,
    data_path: str,
    interpolation: str,
    array_index: Optional[int] = typer.Option(None, "--array-index"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("fcurve.set-interpolation")
    _ok(
        "fcurve.set-interpolation",
        _call_bridge(
            "fcurve.set-interpolation",
            "scene.fcurve.set_interpolation",
            {
                "project": str(project),
                "object_name": object_name,
                "data_path": data_path,
                "interpolation": interpolation,
                "array_index": array_index,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@nla_app.command("track-add")
def nla_track_add(project: Path, object_name: str, track_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("nla.track-add")
    _ok(
        "nla.track-add",
        _call_bridge(
            "nla.track-add",
            "scene.nla.track_add",
            {"project": str(project), "object_name": object_name, "track_name": track_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@action_app.command("list")
def action_list(project: Path) -> None:
    _ok("action.list", _call_bridge("action.list", "scene.action.list", {"project": str(project)}, timeout_seconds=60))


@action_app.command("push-down")
def action_push_down(project: Path, object_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("action.push-down")
    _ok(
        "action.push-down",
        _call_bridge(
            "action.push-down",
            "scene.action.push_down",
            {"project": str(project), "object_name": object_name, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@constraint_app.command("add")
def constraint_add(
    project: Path,
    object_name: str,
    constraint_type: str,
    constraint_name: Optional[str] = typer.Option(None, "--constraint-name"),
    target: Optional[str] = typer.Option(None, "--target"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("constraint.add")
    _ok(
        "constraint.add",
        _call_bridge(
            "constraint.add",
            "scene.constraint.add",
            {
                "project": str(project),
                "object_name": object_name,
                "constraint_type": constraint_type,
                "constraint_name": constraint_name,
                "target": target,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@import_app.command("gltf")
def import_gltf(project: Path, source: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("import.gltf")
    _ok(
        "import.gltf",
        _call_bridge(
            "import.gltf",
            "scene.import.gltf",
            {"project": str(project), "source": str(source), "output": str(output) if output else None},
            timeout_seconds=300,
        ),
    )


@import_app.command("fbx")
def import_fbx(project: Path, source: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("import.fbx")
    _ok(
        "import.fbx",
        _call_bridge(
            "import.fbx",
            "scene.import.fbx",
            {"project": str(project), "source": str(source), "output": str(output) if output else None},
            timeout_seconds=300,
        ),
    )


@import_app.command("obj")
def import_obj(project: Path, source: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("import.obj")
    _ok(
        "import.obj",
        _call_bridge(
            "import.obj",
            "scene.import.obj",
            {"project": str(project), "source": str(source), "output": str(output) if output else None},
            timeout_seconds=300,
        ),
    )


@import_app.command("usd")
def import_usd(project: Path, source: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("import.usd")
    _ok(
        "import.usd",
        _call_bridge(
            "import.usd",
            "scene.import.usd",
            {"project": str(project), "source": str(source), "output": str(output) if output else None},
            timeout_seconds=300,
        ),
    )


@export_app.command("gltf")
def export_gltf(project: Path, target: Path) -> None:
    _ok(
        "export.gltf",
        _call_bridge("export.gltf", "scene.export.gltf", {"project": str(project), "target": str(target)}, timeout_seconds=300),
    )


@export_app.command("fbx")
def export_fbx(project: Path, target: Path) -> None:
    _ok(
        "export.fbx",
        _call_bridge("export.fbx", "scene.export.fbx", {"project": str(project), "target": str(target)}, timeout_seconds=300),
    )


@export_app.command("obj")
def export_obj(project: Path, target: Path) -> None:
    _ok(
        "export.obj",
        _call_bridge("export.obj", "scene.export.obj", {"project": str(project), "target": str(target)}, timeout_seconds=300),
    )


@export_app.command("usd")
def export_usd(project: Path, target: Path) -> None:
    _ok(
        "export.usd",
        _call_bridge("export.usd", "scene.export.usd", {"project": str(project), "target": str(target)}, timeout_seconds=300),
    )


@asset_app.command("list")
def asset_list(project: Path) -> None:
    _ok("asset.list", _call_bridge("asset.list", "scene.asset.list", {"project": str(project)}, timeout_seconds=60))


@asset_app.command("relink-missing")
def asset_relink_missing(project: Path, search_dir: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("asset.relink-missing")
    _ok(
        "asset.relink-missing",
        _call_bridge(
            "asset.relink-missing",
            "scene.asset.relink_missing",
            {"project": str(project), "search_dir": str(search_dir), "output": str(output) if output else None},
            timeout_seconds=300,
        ),
    )


@pack_app.command("resources")
def pack_resources(project: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("pack.resources")
    _ok(
        "pack.resources",
        _call_bridge(
            "pack.resources",
            "scene.pack.resources",
            {"project": str(project), "output": str(output) if output else None},
            timeout_seconds=300,
        ),
    )


@unpack_app.command("resources")
def unpack_resources(project: Path, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("unpack.resources")
    _ok(
        "unpack.resources",
        _call_bridge(
            "unpack.resources",
            "scene.unpack.resources",
            {"project": str(project), "output": str(output) if output else None},
            timeout_seconds=300,
        ),
    )


@render_app.command("still")
def render_still(
    project: Path,
    output_image: Path,
    engine: str = typer.Option("BLENDER_EEVEE", "--engine"),
    samples: int = typer.Option(64, "--samples"),
    resolution_x: int = typer.Option(1920, "--resolution-x"),
    resolution_y: int = typer.Option(1080, "--resolution-y"),
    camera: Optional[str] = typer.Option(None, "--camera"),
) -> None:
    _ensure_bridge_ready("render.still")
    _ok(
        "render.still",
        _call_bridge(
            "render.still",
            "render.still",
            {
                "project": str(project),
                "output_image": str(output_image),
                "engine": engine,
                "samples": samples,
                "resolution_x": resolution_x,
                "resolution_y": resolution_y,
                "camera": camera,
            },
            timeout_seconds=600,
        ),
    )


@render_app.command("animation")
def render_animation(
    project: Path,
    output_dir: Path,
    engine: str = typer.Option("BLENDER_EEVEE", "--engine"),
    frame_start: int = typer.Option(1, "--frame-start"),
    frame_end: int = typer.Option(250, "--frame-end"),
    fps: int = typer.Option(24, "--fps"),
    format: str = typer.Option("PNG", "--format"),
) -> None:
    _ensure_bridge_ready("render.animation")
    _ok(
        "render.animation",
        _call_bridge(
            "render.animation",
            "render.animation",
            {
                "project": str(project),
                "output_dir": str(output_dir),
                "engine": engine,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "fps": fps,
                "format": format,
            },
            timeout_seconds=1800,
        ),
    )


@render_app.command("status")
def render_status(job_id: str) -> None:
    _ok("render.status", _call_bridge("render.status", "render.status", {"job_id": job_id}, timeout_seconds=30))


@render_app.command("cancel")
def render_cancel(job_id: str) -> None:
    _ok("render.cancel", _call_bridge("render.cancel", "render.cancel", {"job_id": job_id}, timeout_seconds=30))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
