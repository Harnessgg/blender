import glob
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


RESULT_PREFIX = "__HARNESS_JSON__"


class BlenderRunError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_blender_bin() -> Path:
    env_path = os.getenv("HARNESS_BLENDER_BIN")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
        raise BlenderRunError("BLENDER_NOT_FOUND", f"HARNESS_BLENDER_BIN does not exist: {env_path}")

    in_path = shutil.which("blender")
    if in_path:
        return Path(in_path)

    windows_candidates = sorted(
        glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"),
        reverse=True,
    )
    if windows_candidates:
        return Path(windows_candidates[0])

    raise BlenderRunError("BLENDER_NOT_FOUND", "Could not find Blender binary. Set HARNESS_BLENDER_BIN.")


def blender_version() -> str:
    blender = resolve_blender_bin()
    try:
        proc = subprocess.run([str(blender), "--version"], capture_output=True, text=True, timeout=10)
    except Exception as exc:
        raise BlenderRunError("BLENDER_EXEC_FAILED", str(exc)) from exc
    if proc.returncode != 0:
        raise BlenderRunError("BLENDER_EXEC_FAILED", (proc.stderr or proc.stdout or "unknown error").strip())
    first_line = (proc.stdout or "").splitlines()
    return first_line[0].strip() if first_line else "unknown"


def run_blender_script(
    script_source: str,
    *,
    blend_file: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout_seconds: float = 60,
) -> Dict[str, Any]:
    blender = resolve_blender_bin()
    with tempfile.TemporaryDirectory(prefix="harness_blender_") as td:
        script_path = Path(td) / "script.py"
        script_path.write_text(script_source, encoding="utf-8")

        cmd = [str(blender), "-b"]
        if blend_file:
            cmd.append(str(blend_file))
        cmd.extend(["--python", str(script_path)])

        env = os.environ.copy()
        env["HARNESS_PARAMS"] = json.dumps(params or {})
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds, env=env)
        except subprocess.TimeoutExpired as exc:
            raise BlenderRunError("BLENDER_EXEC_FAILED", f"Blender timed out after {timeout_seconds}s") from exc
        except Exception as exc:
            raise BlenderRunError("BLENDER_EXEC_FAILED", str(exc)) from exc

        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "unknown blender failure").strip()
            raise BlenderRunError("BLENDER_EXEC_FAILED", msg)

        for line in reversed((proc.stdout or "").splitlines()):
            if line.startswith(RESULT_PREFIX):
                raw = line[len(RESULT_PREFIX) :].strip()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise BlenderRunError("BLENDER_EXEC_FAILED", f"Invalid JSON payload from blender: {exc}") from exc
                if not isinstance(payload, dict):
                    raise BlenderRunError("BLENDER_EXEC_FAILED", "Blender payload must be a JSON object")
                return payload

        raise BlenderRunError("BLENDER_EXEC_FAILED", "Blender completed without result payload")

