## Why

The repository had no root `.gitignore`, so virtualenvs, caches, local env files, and editor cruft could be committed by mistake. A standard Python-oriented ignore list keeps commits clean and matches common FastAPI/uv workflows.

## What Changes

- Add a root `.gitignore` covering bytecode, virtual environments, packaging artifacts, test/coverage caches, common tool caches (mypy, ruff, pytest), secrets (`.env`), and OS/IDE noise.
- **Do not** ignore `uv.lock` or `.python-version` (they stay tracked for reproducible installs and Python pin).
- Brief README note on env files vs `uv.lock`.

## Capabilities

### New Capabilities

- `repo-hygiene`: Requirements for what the Git ignore policy must cover at the repository root.

### Modified Capabilities

- None.

## Impact

- **New file**: `.gitignore` only.
- **Docs**: small README addition.
