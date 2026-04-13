## Context

The repo ships as `starter-template-fastapi` with an empty dependency list and a CLI-style `main.py`. The goal is a minimal but idiomatic FastAPI setup: one `FastAPI` instance exported as `app`, served by Uvicorn (per FastAPI deployment docs), with interactive OpenAPI UIs enabled by default.

## Goals / Non-Goals

**Goals:**

- Declare `fastapi` and `uvicorn[standard]` in `pyproject.toml` so installs pull the framework and a production-capable ASGI server with recommended extras.
- Expose JSON endpoints for service identity (`GET /`) and health (`GET /health` or `/healthz`) suitable for load balancers and local checks.
- Document run commands: `uvicorn main:app --reload` for development and optional `fastapi run main.py` where the CLI is available.

**Non-Goals:**

- Authentication, persistence, background workers, or multi-file package layout (can follow in later changes).
- Docker, CI, or deployment manifests.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ASGI server | Uvicorn with `[standard]` extra | Official FastAPI path; `standard` adds performance-oriented deps (e.g. uvloop) per docs. |
| App shape | Single module `main.py` with `app = FastAPI()` | Smallest viable surface; matches `uvicorn main:app` and `fastapi run main.py` import conventions. |
| Health route | `GET /health` returning JSON `{ "status": "ok" }` | Common convention; easy to probe without HTML. |
| Sync vs async handlers | Sync route functions for trivial I/O | Simpler starter; upgrade to `async def` when I/O-bound work appears. |

**Alternatives considered:** Starlette-only (rejected: user asked for FastAPI); nested `app/` package (deferred: unnecessary for init).

## Risks / Trade-offs

- **Pinning** — Loose version ranges may pull breaking minors → Mitigation: use compatible minimum versions; tighten pins when the project stabilizes.
- **Python 3.14** — Very new; some wheels may lag → Mitigation: keep dependencies mainstream; if install fails, document fallback Python version.

## Migration Plan

Not applicable: greenfield initialization. Rollback is reverting `pyproject.toml`, `main.py`, and docs.

## Open Questions

- None for this scope.
