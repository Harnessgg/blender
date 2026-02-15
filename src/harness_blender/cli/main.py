import json
import os
import shutil
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
mesh_app = typer.Typer(add_completion=False, help="Mesh commands")
lattice_app = typer.Typer(add_completion=False, help="Lattice commands")
curve_app = typer.Typer(add_completion=False, help="Curve commands")
scene_app = typer.Typer(add_completion=False, help="Scene utility commands")
analyze_app = typer.Typer(add_completion=False, help="Analysis commands")
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
app.add_typer(mesh_app, name="mesh")
app.add_typer(lattice_app, name="lattice")
app.add_typer(curve_app, name="curve")
app.add_typer(scene_app, name="scene")
app.add_typer(analyze_app, name="analyze")
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


def _resolve_plan_vars(value: Any, variables: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        out = value
        for k, v in variables.items():
            out = out.replace(f"${{{k}}}", str(v))
        return out
    if isinstance(value, list):
        return [_resolve_plan_vars(v, variables) for v in value]
    if isinstance(value, dict):
        return {k: _resolve_plan_vars(v, variables) for k, v in value.items()}
    return value


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


@bridge_app.command("run-python")
def bridge_run_python(
    script_path: Path,
    project: Optional[Path] = typer.Option(None, "--project"),
    params_json: str = typer.Option("{}", "--params-json"),
    timeout_seconds: int = typer.Option(120, "--timeout-seconds"),
) -> None:
    if not script_path.exists():
        _fail("bridge.run-python", "NOT_FOUND", f"Script not found: {script_path}")
    _ensure_bridge_ready("bridge.run-python")
    _ok(
        "bridge.run-python",
        _call_bridge(
            "bridge.run-python",
            "bridge.run_python",
            {
                "project": str(project) if project else None,
                "code": script_path.read_text(encoding="utf-8"),
                "user_params": json.loads(params_json),
                "timeout_seconds": timeout_seconds,
            },
            timeout_seconds=max(timeout_seconds, 30),
        ),
    )


@app.command("actions")
def actions() -> None:
    _ok("actions", _call_bridge("actions", "system.actions", {}))


@app.command("run-plan")
def run_plan(
    plan_file: Path,
    rollback_on_fail: bool = typer.Option(True, "--rollback-on-fail/--no-rollback-on-fail"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    if not plan_file.exists():
        _fail("run-plan", "NOT_FOUND", f"Plan file not found: {plan_file}")
    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail("run-plan", "INVALID_INPUT", f"Invalid JSON plan: {exc}")
    if not isinstance(plan, dict):
        _fail("run-plan", "INVALID_INPUT", "Plan must be a JSON object")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        _fail("run-plan", "INVALID_INPUT", "Plan must include non-empty 'steps' array")

    variables = dict(plan.get("variables") or {})
    plan_project = plan.get("project")
    if plan_project is not None:
        variables.setdefault("project", plan_project)

    resolved_steps: list[Dict[str, Any]] = []
    for idx, raw in enumerate(steps):
        if not isinstance(raw, dict):
            _fail("run-plan", "INVALID_INPUT", f"Step {idx} must be an object")
        method = raw.get("method")
        if not isinstance(method, str) or not method.strip():
            _fail("run-plan", "INVALID_INPUT", f"Step {idx} missing method")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            _fail("run-plan", "INVALID_INPUT", f"Step {idx} params must be an object")
        params = _resolve_plan_vars(params, variables)
        if "project" not in params and plan_project is not None:
            params["project"] = str(plan_project)
        timeout_seconds = float(raw.get("timeout_seconds", 60))
        resolved_steps.append({"method": method, "params": params, "timeout_seconds": timeout_seconds})

    if dry_run:
        _ok("run-plan", {"dryRun": True, "steps": resolved_steps, "changed": False})
        return

    _ensure_bridge_ready("run-plan")
    client = _bridge_client()

    backup_path: Optional[Path] = None
    project_path: Optional[Path] = None
    if plan_project is not None:
        project_path = Path(str(plan_project))
        if rollback_on_fail and project_path.exists():
            stamp = int(time.time())
            backup_path = project_path.with_suffix(project_path.suffix + f".runplan.{stamp}.bak")
            shutil.copy2(project_path, backup_path)

    results: list[Dict[str, Any]] = []
    for idx, step in enumerate(resolved_steps):
        method = step["method"]
        params = step["params"]
        timeout_seconds = float(step["timeout_seconds"])
        try:
            data = client.call(method, params, timeout_seconds=timeout_seconds)
            results.append({"index": idx, "ok": True, "method": method, "data": data})
        except BridgeClientError as exc:
            rolled_back = False
            rollback_error: Optional[str] = None
            if rollback_on_fail and project_path and backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, project_path)
                    rolled_back = True
                except Exception as rb_exc:
                    rollback_error = str(rb_exc)
            payload = {
                "executed": idx,
                "failedStep": {"index": idx, "method": method, "params": params},
                "error": {"code": exc.code, "message": exc.message},
                "rollbackAttempted": rollback_on_fail and project_path is not None,
                "rolledBack": rolled_back,
                "rollbackError": rollback_error,
                "results": results,
            }
            _print({"ok": False, "protocolVersion": PROTOCOL_VERSION, "command": "run-plan", "data": payload})
            raise SystemExit(ERROR_CODES.get(exc.code, ERROR_CODES["ERROR"]))
    if backup_path and backup_path.exists():
        backup_path.unlink(missing_ok=True)
    _ok("run-plan", {"executed": len(results), "results": results, "changed": True})


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


@object_app.command("transform-many")
def object_transform_many(
    project: Path,
    object_names: list[str],
    location_json: Optional[str] = typer.Option(None, "--location-json"),
    rotation_json: Optional[str] = typer.Option(None, "--rotation-json"),
    scale_json: Optional[str] = typer.Option(None, "--scale-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.transform-many")
    _ok(
        "object.transform-many",
        _call_bridge(
            "object.transform-many",
            "scene.object.transform_many",
            {
                "project": str(project),
                "object_names": object_names,
                "location": json.loads(location_json) if location_json else None,
                "rotation": json.loads(rotation_json) if rotation_json else None,
                "scale": json.loads(scale_json) if scale_json else None,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@object_app.command("boolean-union")
def object_boolean_union(
    project: Path,
    target_object: str,
    with_object: str,
    apply: bool = typer.Option(True, "--apply/--no-apply"),
    delete_with: bool = typer.Option(True, "--delete-with/--keep-with"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.boolean-union")
    _ok(
        "object.boolean-union",
        _call_bridge(
            "object.boolean-union",
            "scene.object.boolean_union",
            {
                "project": str(project),
                "target_object": target_object,
                "with_object": with_object,
                "apply": apply,
                "delete_with": delete_with,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@object_app.command("boolean-difference")
def object_boolean_difference(
    project: Path,
    target_object: str,
    with_object: str,
    apply: bool = typer.Option(True, "--apply/--no-apply"),
    delete_with: bool = typer.Option(False, "--delete-with/--keep-with"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.boolean-difference")
    _ok(
        "object.boolean-difference",
        _call_bridge(
            "object.boolean-difference",
            "scene.object.boolean_difference",
            {
                "project": str(project),
                "target_object": target_object,
                "with_object": with_object,
                "apply": apply,
                "delete_with": delete_with,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@object_app.command("boolean-intersect")
def object_boolean_intersect(
    project: Path,
    target_object: str,
    with_object: str,
    apply: bool = typer.Option(True, "--apply/--no-apply"),
    delete_with: bool = typer.Option(False, "--delete-with/--keep-with"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.boolean-intersect")
    _ok(
        "object.boolean-intersect",
        _call_bridge(
            "object.boolean-intersect",
            "scene.object.boolean_intersect",
            {
                "project": str(project),
                "target_object": target_object,
                "with_object": with_object,
                "apply": apply,
                "delete_with": delete_with,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@object_app.command("join")
def object_join(project: Path, object_names: list[str], output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("object.join")
    _ok(
        "object.join",
        _call_bridge(
            "object.join",
            "scene.object.join",
            {"project": str(project), "object_names": object_names, "output": str(output) if output else None},
            timeout_seconds=120,
        ),
    )


@object_app.command("convert-mesh")
def object_convert_mesh(project: Path, object_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("object.convert-mesh")
    _ok(
        "object.convert-mesh",
        _call_bridge(
            "object.convert-mesh",
            "scene.object.convert_mesh",
            {"project": str(project), "object_name": object_name, "output": str(output) if output else None},
            timeout_seconds=120,
        ),
    )


@object_app.command("shrinkwrap")
def object_shrinkwrap(
    project: Path,
    object_name: str,
    target_object: str,
    wrap_method: str = typer.Option("NEAREST_SURFACEPOINT", "--wrap-method"),
    offset: float = typer.Option(0.0, "--offset"),
    apply: bool = typer.Option(True, "--apply/--no-apply"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.shrinkwrap")
    _ok(
        "object.shrinkwrap",
        _call_bridge(
            "object.shrinkwrap",
            "scene.object.shrinkwrap",
            {
                "project": str(project),
                "object_name": object_name,
                "target_object": target_object,
                "wrap_method": wrap_method,
                "offset": offset,
                "apply": apply,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@object_app.command("data-transfer")
def object_data_transfer(
    project: Path,
    object_name: str,
    target_object: str,
    data_domain: str = typer.Option("LOOP", "--data-domain"),
    data_type: str = typer.Option("CUSTOM_NORMAL", "--data-type"),
    apply: bool = typer.Option(True, "--apply/--no-apply"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.data-transfer")
    _ok(
        "object.data-transfer",
        _call_bridge(
            "object.data-transfer",
            "scene.object.data_transfer",
            {
                "project": str(project),
                "object_name": object_name,
                "target_object": target_object,
                "data_domain": data_domain,
                "data_type": data_type,
                "apply": apply,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@object_app.command("group-create")
def object_group_create(
    project: Path,
    group_name: str,
    object_names: list[str],
    location_json: str = typer.Option("[0,0,0]", "--location-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.group-create")
    _ok(
        "object.group-create",
        _call_bridge(
            "object.group-create",
            "scene.object.group_create",
            {
                "project": str(project),
                "group_name": group_name,
                "object_names": object_names,
                "location": json.loads(location_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@object_app.command("parent-many")
def object_parent_many(
    project: Path,
    parent_name: str,
    child_names: list[str],
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("object.parent-many")
    _ok(
        "object.parent-many",
        _call_bridge(
            "object.parent-many",
            "scene.object.parent_many",
            {"project": str(project), "parent_name": parent_name, "child_names": child_names, "output": str(output) if output else None},
            timeout_seconds=120,
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


@camera_app.command("look-at")
def camera_look_at(
    project: Path,
    camera_name: str,
    target_object: Optional[str] = typer.Option(None, "--target-object"),
    target_location_json: Optional[str] = typer.Option(None, "--target-location-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("camera.look-at")
    _ok(
        "camera.look-at",
        _call_bridge(
            "camera.look-at",
            "scene.camera.look_at",
            {
                "project": str(project),
                "camera_name": camera_name,
                "target_object": target_object,
                "target_location": json.loads(target_location_json) if target_location_json else None,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@camera_app.command("rig-product-shot")
def camera_rig_product_shot(
    project: Path,
    target_object: str,
    camera_name: str = typer.Option("ProductCam", "--camera-name"),
    distance: float = typer.Option(4.0, "--distance"),
    height: float = typer.Option(1.2, "--height"),
    lens: float = typer.Option(60.0, "--lens"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("camera.rig-product-shot")
    _ok(
        "camera.rig-product-shot",
        _call_bridge(
            "camera.rig-product-shot",
            "scene.camera.rig_product_shot",
            {
                "project": str(project),
                "target_object": target_object,
                "camera_name": camera_name,
                "distance": distance,
                "height": height,
                "lens": lens,
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


@light_app.command("rig-three-point")
def light_rig_three_point(
    project: Path,
    target_object: Optional[str] = typer.Option(None, "--target-object"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("light.rig-three-point")
    _ok(
        "light.rig-three-point",
        _call_bridge(
            "light.rig-three-point",
            "scene.light.rig_three_point",
            {"project": str(project), "target_object": target_object, "output": str(output) if output else None},
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


@material_app.command("assign-many")
def material_assign_many(
    project: Path,
    material_name: str,
    object_names: list[str],
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("material.assign-many")
    _ok(
        "material.assign-many",
        _call_bridge(
            "material.assign-many",
            "scene.material.assign_many",
            {"project": str(project), "material_name": material_name, "object_names": object_names, "output": str(output) if output else None},
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


@material_app.command("set-node-input")
def material_set_node_input(
    project: Path,
    material_name: str,
    node_name: str,
    input_name: str,
    value_json: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("material.set-node-input")
    _ok(
        "material.set-node-input",
        _call_bridge(
            "material.set-node-input",
            "scene.material.set_node_input",
            {
                "project": str(project),
                "material_name": material_name,
                "node_name": node_name,
                "input_name": input_name,
                "value": json.loads(value_json),
                "output": str(output) if output else None,
            },
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


@modifier_app.command("set")
def modifier_set(
    project: Path,
    object_name: str,
    modifier_name: str,
    property_name: str,
    value_json: str,
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("modifier.set")
    _ok(
        "modifier.set",
        _call_bridge(
            "modifier.set",
            "scene.modifier.set",
            {
                "project": str(project),
                "object_name": object_name,
                "modifier_name": modifier_name,
                "property_name": property_name,
                "value": json.loads(value_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@mesh_app.command("smooth")
def mesh_smooth(
    project: Path,
    object_name: str,
    iterations: int = typer.Option(5, "--iterations"),
    factor: float = typer.Option(0.5, "--factor"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.smooth")
    _ok(
        "mesh.smooth",
        _call_bridge(
            "mesh.smooth",
            "scene.mesh.smooth",
            {
                "project": str(project),
                "object_name": object_name,
                "iterations": iterations,
                "factor": factor,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("subdivide")
def mesh_subdivide(
    project: Path,
    object_name: str,
    cuts: int = typer.Option(1, "--cuts"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.subdivide")
    _ok(
        "mesh.subdivide",
        _call_bridge(
            "mesh.subdivide",
            "scene.mesh.subdivide",
            {"project": str(project), "object_name": object_name, "cuts": cuts, "output": str(output) if output else None},
            timeout_seconds=120,
        ),
    )


@mesh_app.command("select-verts")
def mesh_select_verts(
    project: Path,
    object_name: str,
    indices_json: str,
    replace: bool = typer.Option(True, "--replace/--add"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.select-verts")
    _ok(
        "mesh.select-verts",
        _call_bridge(
            "mesh.select-verts",
            "scene.mesh.select_verts",
            {
                "project": str(project),
                "object_name": object_name,
                "indices": json.loads(indices_json),
                "replace": replace,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("clear-selection")
def mesh_clear_selection(project: Path, object_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("mesh.clear-selection")
    _ok(
        "mesh.clear-selection",
        _call_bridge(
            "mesh.clear-selection",
            "scene.mesh.clear_selection",
            {"project": str(project), "object_name": object_name, "output": str(output) if output else None},
            timeout_seconds=120,
        ),
    )


@mesh_app.command("transform-selected")
def mesh_transform_selected(
    project: Path,
    object_name: str,
    location_json: str = typer.Option("[0,0,0]", "--location-json"),
    rotation_json: str = typer.Option("[0,0,0]", "--rotation-json"),
    scale_json: str = typer.Option("[1,1,1]", "--scale-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.transform-selected")
    _ok(
        "mesh.transform-selected",
        _call_bridge(
            "mesh.transform-selected",
            "scene.mesh.transform_selected",
            {
                "project": str(project),
                "object_name": object_name,
                "location": json.loads(location_json),
                "rotation": json.loads(rotation_json),
                "scale": json.loads(scale_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("proportional-edit")
def mesh_proportional_edit(
    project: Path,
    object_name: str,
    location_json: str = typer.Option("[0,0,0]", "--location-json"),
    scale_json: str = typer.Option("[1,1,1]", "--scale-json"),
    falloff: str = typer.Option("SMOOTH", "--falloff"),
    radius: float = typer.Option(1.0, "--radius"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.proportional-edit")
    _ok(
        "mesh.proportional-edit",
        _call_bridge(
            "mesh.proportional-edit",
            "scene.mesh.proportional_edit",
            {
                "project": str(project),
                "object_name": object_name,
                "location": json.loads(location_json),
                "scale": json.loads(scale_json),
                "falloff": falloff,
                "radius": radius,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("extrude-region")
def mesh_extrude_region(
    project: Path,
    object_name: str,
    offset_json: str = typer.Option("[0,0,0.1]", "--offset-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.extrude-region")
    _ok(
        "mesh.extrude-region",
        _call_bridge(
            "mesh.extrude-region",
            "scene.mesh.extrude_region",
            {
                "project": str(project),
                "object_name": object_name,
                "offset": json.loads(offset_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("bevel-verts")
def mesh_bevel_verts(
    project: Path,
    object_name: str,
    amount: float = typer.Option(0.02, "--amount"),
    segments: int = typer.Option(2, "--segments"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.bevel-verts")
    _ok(
        "mesh.bevel-verts",
        _call_bridge(
            "mesh.bevel-verts",
            "scene.mesh.bevel_verts",
            {
                "project": str(project),
                "object_name": object_name,
                "amount": amount,
                "segments": segments,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("merge-by-distance")
def mesh_merge_by_distance(
    project: Path,
    object_name: str,
    distance: float = typer.Option(0.0001, "--distance"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.merge-by-distance")
    _ok(
        "mesh.merge-by-distance",
        _call_bridge(
            "mesh.merge-by-distance",
            "scene.mesh.merge_by_distance",
            {
                "project": str(project),
                "object_name": object_name,
                "distance": distance,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("loop-cut")
def mesh_loop_cut(
    project: Path,
    object_name: str,
    edge_indices_json: str,
    cuts: int = typer.Option(1, "--cuts"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.loop-cut")
    _ok(
        "mesh.loop-cut",
        _call_bridge(
            "mesh.loop-cut",
            "scene.mesh.loop_cut",
            {
                "project": str(project),
                "object_name": object_name,
                "edge_indices": json.loads(edge_indices_json),
                "cuts": cuts,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("slide-loop")
def mesh_slide_loop(
    project: Path,
    object_name: str,
    edge_indices_json: str,
    factor: float = typer.Option(0.0, "--factor"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.slide-loop")
    _ok(
        "mesh.slide-loop",
        _call_bridge(
            "mesh.slide-loop",
            "scene.mesh.slide_loop",
            {
                "project": str(project),
                "object_name": object_name,
                "edge_indices": json.loads(edge_indices_json),
                "factor": factor,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("bisect")
def mesh_bisect(
    project: Path,
    object_name: str,
    plane_co_json: str = typer.Option("[0,0,0]", "--plane-co-json"),
    plane_no_json: str = typer.Option("[0,0,1]", "--plane-no-json"),
    clear_inner: bool = typer.Option(False, "--clear-inner/--keep-inner"),
    clear_outer: bool = typer.Option(False, "--clear-outer/--keep-outer"),
    use_fill: bool = typer.Option(False, "--use-fill/--no-fill"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.bisect")
    _ok(
        "mesh.bisect",
        _call_bridge(
            "mesh.bisect",
            "scene.mesh.bisect",
            {
                "project": str(project),
                "object_name": object_name,
                "plane_co": json.loads(plane_co_json),
                "plane_no": json.loads(plane_no_json),
                "clear_inner": clear_inner,
                "clear_outer": clear_outer,
                "use_fill": use_fill,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@mesh_app.command("clean")
def mesh_clean(
    project: Path,
    object_name: str,
    merge_distance: float = typer.Option(0.0001, "--merge-distance"),
    dissolve_angle: float = typer.Option(0.01, "--dissolve-angle"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("mesh.clean")
    _ok(
        "mesh.clean",
        _call_bridge(
            "mesh.clean",
            "scene.mesh.clean",
            {
                "project": str(project),
                "object_name": object_name,
                "merge_distance": merge_distance,
                "dissolve_angle": dissolve_angle,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@lattice_app.command("add")
def lattice_add(
    project: Path,
    name: str = typer.Option("Lattice", "--name"),
    location_json: str = typer.Option("[0,0,0]", "--location-json"),
    scale_json: str = typer.Option("[1,1,1]", "--scale-json"),
    points_u: int = typer.Option(2, "--points-u"),
    points_v: int = typer.Option(2, "--points-v"),
    points_w: int = typer.Option(2, "--points-w"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("lattice.add")
    _ok(
        "lattice.add",
        _call_bridge(
            "lattice.add",
            "scene.lattice.add",
            {
                "project": str(project),
                "name": name,
                "location": json.loads(location_json),
                "scale": json.loads(scale_json),
                "points_u": points_u,
                "points_v": points_v,
                "points_w": points_w,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@lattice_app.command("bind")
def lattice_bind(
    project: Path,
    object_name: str,
    lattice_name: str,
    modifier_name: str = typer.Option("Lattice", "--modifier-name"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("lattice.bind")
    _ok(
        "lattice.bind",
        _call_bridge(
            "lattice.bind",
            "scene.lattice.bind",
            {
                "project": str(project),
                "object_name": object_name,
                "lattice_name": lattice_name,
                "modifier_name": modifier_name,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@lattice_app.command("set-point")
def lattice_set_point(
    project: Path,
    lattice_name: str,
    u: int,
    v: int,
    w: int,
    location_json: str = typer.Option("[0,0,0]", "--location-json"),
    delta: bool = typer.Option(False, "--delta/--absolute"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("lattice.set-point")
    _ok(
        "lattice.set-point",
        _call_bridge(
            "lattice.set-point",
            "scene.lattice.set_point",
            {
                "project": str(project),
                "lattice_name": lattice_name,
                "u": u,
                "v": v,
                "w": w,
                "location": json.loads(location_json),
                "delta": delta,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@curve_app.command("add-bezier")
def curve_add_bezier(
    project: Path,
    points_json: str,
    name: str = typer.Option("BezierCurve", "--name"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("curve.add-bezier")
    _ok(
        "curve.add-bezier",
        _call_bridge(
            "curve.add-bezier",
            "scene.curve.add_bezier",
            {
                "project": str(project),
                "name": name,
                "points": json.loads(points_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@curve_app.command("set-handle")
def curve_set_handle(
    project: Path,
    curve_name: str,
    point_index: int,
    handle_location_json: str,
    handle: str = typer.Option("left", "--handle"),
    handle_type: Optional[str] = typer.Option(None, "--handle-type"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("curve.set-handle")
    _ok(
        "curve.set-handle",
        _call_bridge(
            "curve.set-handle",
            "scene.curve.set_handle",
            {
                "project": str(project),
                "curve_name": curve_name,
                "point_index": point_index,
                "handle": handle,
                "handle_location": json.loads(handle_location_json),
                "handle_type": handle_type,
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@curve_app.command("to-mesh")
def curve_to_mesh(project: Path, curve_name: str, output: Optional[Path] = typer.Option(None, "--output")) -> None:
    _ensure_bridge_ready("curve.to-mesh")
    _ok(
        "curve.to-mesh",
        _call_bridge(
            "curve.to-mesh",
            "scene.curve.to_mesh",
            {"project": str(project), "curve_name": curve_name, "output": str(output) if output else None},
            timeout_seconds=120,
        ),
    )


@scene_app.command("add-reference-image")
def scene_add_reference_image(
    project: Path,
    image_path: Path,
    name: str = typer.Option("ReferenceImage", "--name"),
    location_json: str = typer.Option("[0,0,0]", "--location-json"),
    scale_json: str = typer.Option("[1,1,1]", "--scale-json"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("scene.add-reference-image")
    _ok(
        "scene.add-reference-image",
        _call_bridge(
            "scene.add-reference-image",
            "scene.add_reference_image",
            {
                "project": str(project),
                "image_path": str(image_path),
                "name": name,
                "location": json.loads(location_json),
                "scale": json.loads(scale_json),
                "output": str(output) if output else None,
            },
            timeout_seconds=120,
        ),
    )


@scene_app.command("set-orthographic")
def scene_set_orthographic(
    project: Path,
    camera_name: str,
    ortho_scale: float = typer.Option(2.0, "--ortho-scale"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("scene.set-orthographic")
    _ok(
        "scene.set-orthographic",
        _call_bridge(
            "scene.set-orthographic",
            "scene.set_orthographic",
            {"project": str(project), "camera_name": camera_name, "ortho_scale": ortho_scale, "output": str(output) if output else None},
            timeout_seconds=120,
        ),
    )


@scene_app.command("set-world-background")
def scene_set_world_background(
    project: Path,
    color: str = typer.Option("#000000", "--color"),
    strength: float = typer.Option(1.0, "--strength"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("scene.set-world-background")
    _ok(
        "scene.set-world-background",
        _call_bridge(
            "scene.set-world-background",
            "scene.world.set_background",
            {"project": str(project), "color": color, "strength": strength, "output": str(output) if output else None},
            timeout_seconds=60,
        ),
    )


@scene_app.command("set-color-management")
def scene_set_color_management(
    project: Path,
    view_transform: Optional[str] = typer.Option(None, "--view-transform"),
    look: Optional[str] = typer.Option(None, "--look"),
    exposure: Optional[float] = typer.Option(None, "--exposure"),
    gamma: Optional[float] = typer.Option(None, "--gamma"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    _ensure_bridge_ready("scene.set-color-management")
    _ok(
        "scene.set-color-management",
        _call_bridge(
            "scene.set-color-management",
            "scene.color_management.set",
            {
                "project": str(project),
                "view_transform": view_transform,
                "look": look,
                "exposure": exposure,
                "gamma": gamma,
                "output": str(output) if output else None,
            },
            timeout_seconds=60,
        ),
    )


@analyze_app.command("silhouette-diff")
def analyze_silhouette_diff(
    project: Path,
    source_image: Path,
    reference_image: Path,
    threshold: float = typer.Option(0.1, "--threshold"),
) -> None:
    _ensure_bridge_ready("analyze.silhouette-diff")
    _ok(
        "analyze.silhouette-diff",
        _call_bridge(
            "analyze.silhouette-diff",
            "analyze.silhouette_diff",
            {
                "project": str(project),
                "source_image": str(source_image),
                "reference_image": str(reference_image),
                "threshold": threshold,
            },
            timeout_seconds=120,
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
