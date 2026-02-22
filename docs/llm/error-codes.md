# Error Codes

- `ERROR` -> exit `1`
- `NOT_FOUND` -> exit `2`
- `VALIDATION_FAILED` -> exit `3`
- `INVALID_INPUT` -> exit `4`
- `BRIDGE_UNAVAILABLE` -> exit `5`

Retry guidance:
- Retry only on `BRIDGE_UNAVAILABLE`.
- Recommended backoff: `0.5s`, `1s`, `2s`.
- Re-check bridge with `harnessgg-blender bridge status` before retrying mutating commands.

