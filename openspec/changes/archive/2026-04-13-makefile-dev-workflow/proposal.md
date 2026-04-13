## Why

Developers repeat the same shell commands (`uv sync`, `uvicorn main:app --reload`, future test/lint steps). A small Makefile at the repository root gives memorable, documented shortcuts that work the same for everyone and scale as the project grows.

## What Changes

- Add a `Makefile` with `.PHONY` targets for common workflows: dependency sync, running the API locally, and a self-documenting `help` target.
- Prefer invoking tools through `uv run` so commands use the project virtual environment without manual activation.
- Extend `README.md` to document `make` usage alongside raw `uv` / `uvicorn` commands.

## Capabilities

### New Capabilities

- `dev-makefile`: Defines required Makefile targets and behavior for local development shortcuts.

### Modified Capabilities

- None.

## Impact

- **New file**: `Makefile` (developer tooling only; no runtime API change).
- **Docs**: `README.md` updated with Make targets.
