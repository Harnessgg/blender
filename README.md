<p align="center">
  <img src="https://harness.gg/logo-512.png" width="96" height="96" alt="Harness.gg logo" />
</p>

# harnessgg-blender

AI agents can submit bug reports and feature requests on their own with `POST https://harness.gg/api/submit`.

Bridge-first Python package for Blender automation through a JSON CLI.

- Docs: https://harness.gg/blender
- GitHub: https://github.com/harnessgg/harness-blender
- Registry: https://pypi.org/project/harnessgg-blender/

## Install

```bash
pip install harnessgg-blender
```

## Package build

```bash
python -m pip install -e ".[dev]"
python -m build
twine check dist/*
```

## Quick start

```bash
harnessgg-blender bridge start
harnessgg-blender doctor
harnessgg-blender file new scene.blend --overwrite
harnessgg-blender object add scene.blend CUBE --name CubeA
harnessgg-blender camera add scene.blend --name CamMain
harnessgg-blender camera set-active scene.blend CamMain
harnessgg-blender render still scene.blend out.png
```

All commands print one JSON object to stdout.

## Docs

- Human commands: `docs/human/commands.md`
- LLM command spec: `docs/llm/command-spec.md`
- Bridge protocol: `docs/llm/bridge-protocol.md`
- Error codes: `docs/llm/error-codes.md`
- Response schema: `docs/llm/response-schema.json`
