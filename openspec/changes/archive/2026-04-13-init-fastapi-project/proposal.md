## Why

The repository is a Python package scaffold without a web stack. We need a production-oriented FastAPI baseline so the project can expose HTTP APIs, ship automatic OpenAPI documentation, and run locally with a standard ASGI server (Uvicorn), aligned with current FastAPI guidance.

## What Changes

- Add FastAPI and Uvicorn (with recommended extras) as project dependencies in `pyproject.toml`.
- Replace the placeholder `main.py` with a FastAPI `app` exposing a root message, a liveness/health route, and relying on built-in `/docs` and `/redoc`.
- Document how to install dependencies and run the app (`uvicorn` or `fastapi run`).
- Keep the layout minimal (single-module app) so future features can grow into a package layout without rewriting the spec.

## Capabilities

### New Capabilities

- `api-core`: Defines the public HTTP surface of the starter—root and health endpoints, JSON responses, and availability of interactive API documentation.

### Modified Capabilities

- None (no existing specs under `openspec/specs/`).

## Impact

- **Dependencies**: New runtime deps—`fastapi`, `uvicorn[standard]` (or equivalent pinned ranges in `pyproject.toml`).
- **Code**: `main.py` becomes the ASGI entrypoint; `pyproject.toml` and `README.md` updated for run instructions.
- **APIs**: New HTTP routes on the default port when dev server runs; no external services required.
