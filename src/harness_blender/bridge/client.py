import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from harness_blender.bridge.protocol import PROTOCOL_VERSION


class BridgeClientError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class BridgeClient:
    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv("HARNESS_BLENDER_BRIDGE_URL", "http://127.0.0.1:41749")

    def call(self, method: str, params: Dict[str, Any], timeout_seconds: float = 30) -> Dict[str, Any]:
        payload = json.dumps({"id": method, "method": method, "params": params}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/rpc",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
                error = body.get("error", {})
                raise BridgeClientError(error.get("code", "ERROR"), error.get("message", str(exc))) from exc
            except json.JSONDecodeError:
                raise BridgeClientError("ERROR", str(exc)) from exc
        except Exception as exc:
            raise BridgeClientError("BRIDGE_UNAVAILABLE", str(exc)) from exc

        if body.get("protocolVersion") != PROTOCOL_VERSION:
            raise BridgeClientError(
                "ERROR", f"Protocol mismatch: expected {PROTOCOL_VERSION}, got {body.get('protocolVersion')}"
            )
        if not body.get("ok", False):
            error = body.get("error", {})
            raise BridgeClientError(error.get("code", "ERROR"), error.get("message", "Bridge call failed"))
        return body["result"]

    def health(self) -> Dict[str, Any]:
        request = urllib.request.Request(f"{self.url}/health", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise BridgeClientError("BRIDGE_UNAVAILABLE", str(exc)) from exc
