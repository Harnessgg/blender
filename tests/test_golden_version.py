import json
import subprocess


def test_golden_version_keys() -> None:
    proc = subprocess.run(["harnessgg-blender", "version"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert sorted(payload.keys()) == ["command", "data", "ok", "protocolVersion"]
    assert sorted(payload["data"].keys()) == ["harnessVersion", "warnings"]

