# harness-blender

Bridge-first Python package for agent-driven Blender automation through a JSON CLI.

## Install (local)

```bash
pip install -e .
```

## Quick Start

```bash
harness-blender bridge start
harness-blender doctor
harness-blender file new scene.blend --overwrite
harness-blender object add scene.blend CUBE --name CubeA
harness-blender camera add scene.blend --name CamMain
harness-blender camera set-active scene.blend CamMain
harness-blender render still scene.blend out.png
```

## Docs

- Human commands: `docs/human/commands.md`
- LLM command spec: `docs/llm/command-spec.md`
- Bridge protocol: `docs/llm/bridge-protocol.md`
- Error codes: `docs/llm/error-codes.md`
- Response schema: `docs/llm/response-schema.json`

## Publishing

Build and validate locally:

```bash
python -m pip install -e ".[dev]"
python -m build
twine check dist/*
```

Automated publish is configured in `.github/workflows/publish.yaml` using trusted publishing
(`environment: pypi` + OIDC).
