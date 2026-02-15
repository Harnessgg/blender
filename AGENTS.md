# Repository Guidelines

## Project Structure & Module Organization
- Core package code lives in `src/harness_blender/`.
- CLI entrypoints are in `src/harness_blender/cli/` (`main.py`).
- Bridge protocol/client/server/operations are in `src/harness_blender/bridge/`.
- Tests live in `tests/` (contract and golden response checks).
- Human and LLM-facing docs are in `docs/human/` and `docs/llm/`.
- Temporary render/project outputs should go to `tmp/` and should not be committed.

## Build, Test, and Development Commands
- Install editable package:
  - `python -m pip install -e .`
- Run CLI locally:
  - `harness-blender version`
  - `harness-blender bridge start`
- Run tests:
  - `python -m pytest -q`
- Compile-check Python modules:
  - `python -m compileall src`

## Coding Style & Naming Conventions
- Language: Python 3.10+.
- Use 4-space indentation and keep code ASCII unless required otherwise.
- Prefer explicit, small helper functions over large monolithic handlers.
- File/module naming: `snake_case`.
- CLI command naming: Blender-native verbs/nouns (`object add`, `material assign`, `render still`).
- Bridge RPC method naming: dotted snake case (`scene.object.add`, `render.animation`).

## Testing Guidelines
- Framework: `pytest`.
- Add tests under `tests/` named `test_*.py`.
- Keep tests deterministic; validate JSON envelope fields (`ok`, `protocolVersion`, `command`, `data`/`error`).
- For new commands, add at least:
  - one success-path check
  - one failure-path check (invalid input or missing file)

## Commit & Pull Request Guidelines
- This folder currently has no accessible Git history; use Conventional Commits by default:
  - `feat: add scene.light.set_color`
  - `fix: verify render output file exists`
- PRs should include:
  - scope summary and rationale
  - commands used to test (`pytest`, smoke CLI calls)
  - updated docs when command surfaces change
  - sample JSON output for new CLI/RPC methods

## Security & Configuration Tips
- Prefer local bridge URL only (`127.0.0.1`).
- Set Blender path via `HARNESS_BLENDER_BIN` when auto-detection is unreliable.
- Do not commit local machine paths, rendered media, or temporary `.blend` artifacts.
