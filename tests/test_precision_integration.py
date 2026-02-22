import json
import os
import subprocess
from pathlib import Path

import pytest


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["harnessgg-blender", *args], capture_output=True, text=True, check=False)


def _require_integration() -> None:
    if os.getenv("HARNESS_BLENDER_INTEGRATION") != "1":
        pytest.skip("Set HARNESS_BLENDER_INTEGRATION=1 to run Blender integration tests")


def _ensure_bridge() -> None:
    status = _run("bridge", "status")
    if status.returncode == 0:
        return
    started = _run("bridge", "start")
    assert started.returncode == 0, started.stdout + started.stderr


def test_precision_command_families() -> None:
    _require_integration()
    _ensure_bridge()
    project = Path("tmp/test_precision_integration.blend")
    assert _run("file", "new", str(project), "--overwrite").returncode == 0
    assert _run("object", "add", str(project), "CUBE", "--name", "MeshA", "--output", str(project)).returncode == 0
    assert _run("object", "add", str(project), "SPHERE", "--name", "MeshB", "--location-json", "[0.8,0,0]", "--output", str(project)).returncode == 0
    assert _run("mesh", "loop-cut", str(project), "MeshA", "[0,1,2,3]", "--cuts", "1", "--output", str(project)).returncode == 0
    assert _run("mesh", "slide-loop", str(project), "MeshA", "[0,1,2,3]", "--factor", "0.1", "--output", str(project)).returncode == 0
    assert _run("lattice", "add", str(project), "--name", "Cage", "--points-u", "2", "--points-v", "2", "--points-w", "3", "--output", str(project)).returncode == 0
    assert _run("lattice", "bind", str(project), "MeshA", "Cage", "--output", str(project)).returncode == 0
    assert _run("lattice", "set-point", str(project), "Cage", "1", "1", "2", "--location-json", "[0,0,0.25]", "--delta", "--output", str(project)).returncode == 0
    assert _run("curve", "add-bezier", str(project), "[[0,0,0],[0.2,0,0.6],[0,0,1.0]]", "--name", "ProfileCurve", "--output", str(project)).returncode == 0
    assert _run("curve", "set-handle", str(project), "ProfileCurve", "1", "[0.4,0,0.6]", "--handle", "right", "--handle-type", "FREE", "--output", str(project)).returncode == 0
    assert _run("curve", "to-mesh", str(project), "ProfileCurve", "--output", str(project)).returncode == 0
    assert _run("object", "shrinkwrap", str(project), "MeshA", "MeshB", "--apply", "--output", str(project)).returncode == 0
    assert _run("object", "data-transfer", str(project), "MeshA", "MeshB", "--data-domain", "LOOP", "--data-type", "CUSTOM_NORMAL", "--apply", "--output", str(project)).returncode == 0


def test_cascade_silhouette_threshold() -> None:
    _require_integration()
    _ensure_bridge()
    project = Path("tmp/test_cascade_threshold.blend")
    render = Path("tmp/test_cascade_threshold.png")
    ref = Path("tmp/cascade.png")
    assert ref.exists()
    assert _run("file", "new", str(project), "--overwrite").returncode == 0
    assert _run("object", "add", str(project), "SPHERE", "--name", "Drop", "--scale-json", "[0.9,0.9,1.1]", "--output", str(project)).returncode == 0
    assert _run("camera", "add", str(project), "--name", "RefCam", "--location-json", "[0,-4,0.8]", "--rotation-json", "[1.5708,0,0]", "--output", str(project)).returncode == 0
    assert _run("scene", "set-orthographic", str(project), "RefCam", "--ortho-scale", "2.8", "--output", str(project)).returncode == 0
    assert _run("render", "still", str(project), str(render), "--resolution-x", "256", "--resolution-y", "256", "--samples", "8", "--camera", "RefCam").returncode == 0
    diff_proc = _run("analyze", "silhouette-diff", str(project), str(render), str(ref), "--threshold", "0.1")
    assert diff_proc.returncode == 0, diff_proc.stdout + diff_proc.stderr
    payload = json.loads(diff_proc.stdout)
    iou = float(payload["data"]["iou"])
    assert iou >= 0.05
