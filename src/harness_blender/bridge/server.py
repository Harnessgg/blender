import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from harness_blender.bridge.operations import BridgeOperationError, execute
from harness_blender.bridge.protocol import PROTOCOL_VERSION


class BridgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "HarnessBlenderBridge/1.0"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/rpc":
            self._send(404, {"ok": False, "error": {"code": "NOT_FOUND", "message": "Route not found"}})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body)
            method = payload.get("method")
            params = payload.get("params", {})
            request_id = payload.get("id")
            result = execute(method, params)
            self._send(
                200,
                {
                    "ok": True,
                    "protocolVersion": PROTOCOL_VERSION,
                    "id": request_id,
                    "result": result,
                },
            )
        except BridgeOperationError as exc:
            self._send(
                400,
                {
                    "ok": False,
                    "protocolVersion": PROTOCOL_VERSION,
                    "error": {"code": exc.code, "message": exc.message},
                },
            )
        except Exception as exc:
            self._send(
                500,
                {
                    "ok": False,
                    "protocolVersion": PROTOCOL_VERSION,
                    "error": {"code": "ERROR", "message": str(exc)},
                },
            )

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True, "protocolVersion": PROTOCOL_VERSION, "status": "ok"})
            return
        self._send(404, {"ok": False, "error": {"code": "NOT_FOUND", "message": "Route not found"}})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_bridge_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), BridgeRequestHandler)


def run_bridge_server(host: str, port: int) -> None:
    server = create_bridge_server(host, port)
    server.serve_forever()

