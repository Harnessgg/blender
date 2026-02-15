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

