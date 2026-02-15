# Bridge Protocol

Transport: HTTP JSON over localhost.

- Health: `GET /health`
- RPC: `POST /rpc`

Request:

```json
{
  "id": "scene.object.list",
  "method": "scene.object.list",
  "params": {
    "project": "C:/path/scene.blend"
  }
}
```

Success:

```json
{
  "ok": true,
  "protocolVersion": "1.0",
  "id": "scene.object.list",
  "result": {}
}
```

Error:

```json
{
  "ok": false,
  "protocolVersion": "1.0",
  "error": {
    "code": "INVALID_INPUT",
    "message": "Unknown method"
  }
}
```

