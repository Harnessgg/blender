import json
import subprocess


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["harness-blender", *args], capture_output=True, text=True, check=False)


def test_version_envelope() -> None:
    proc = _run("version")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "version"
    assert "protocolVersion" in payload
    assert isinstance(payload["data"], dict)


def test_bridge_status_envelope_shape() -> None:
    proc = _run("bridge", "status")
    payload = json.loads(proc.stdout)
    assert "ok" in payload
    assert "protocolVersion" in payload
    assert "command" in payload
    if payload["ok"]:
        assert "data" in payload
    else:
        assert "error" in payload


def test_mesh_help_lists_precision_commands() -> None:
    proc = _run("mesh", "--help")
    assert proc.returncode == 0
    out = proc.stdout
    assert "select-verts" in out
    assert "transform-selected" in out
    assert "proportional-edit" in out
    assert "loop-cut" in out


def test_scene_and_analyze_help_available() -> None:
    scene_proc = _run("scene", "--help")
    analyze_proc = _run("analyze", "--help")
    assert scene_proc.returncode == 0
    assert analyze_proc.returncode == 0
    assert "add-reference-image" in scene_proc.stdout
    assert "set-orthographic" in scene_proc.stdout
    assert "silhouette-diff" in analyze_proc.stdout


def test_lattice_and_curve_help_available() -> None:
    lattice_proc = _run("lattice", "--help")
    curve_proc = _run("curve", "--help")
    assert lattice_proc.returncode == 0
    assert curve_proc.returncode == 0
    assert "set-point" in lattice_proc.stdout
    assert "add-bezier" in curve_proc.stdout
    assert "to-mesh" in curve_proc.stdout


def test_actions_include_precision_methods() -> None:
    proc = _run("actions")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    actions = payload["data"]["actions"]
    assert "scene.mesh.slide_loop" in actions
    assert "scene.lattice.add" in actions
    assert "scene.curve.to_mesh" in actions
    assert "scene.object.shrinkwrap" in actions
    assert "scene.object.data_transfer" in actions
    assert "scene.world.set_background" in actions
    assert "scene.color_management.set" in actions
    assert "scene.camera.look_at" in actions
    assert "scene.material.set_node_input" in actions
    assert "scene.mesh.bisect" in actions
    assert "scene.mesh.clean" in actions
    assert "scene.object.group_create" in actions
    assert "scene.object.parent_many" in actions
    assert "scene.object.transform_many" in actions
    assert "scene.material.assign_many" in actions
    assert "scene.light.rig_three_point" in actions
    assert "scene.camera.rig_product_shot" in actions


def test_run_plan_help_available() -> None:
    proc = _run("run-plan", "--help")
    assert proc.returncode == 0
    assert "rollback-on-fail" in proc.stdout
    assert "dry-run" in proc.stdout
