## Context

The stack uses [uv](https://docs.astral.sh/uv/) for dependencies and Uvicorn for the ASGI server. Contributors should not need to memorize long commands or hunt through README sections for copy-paste snippets.

## Goals / Non-Goals

**Goals:**

- Provide a default `make` or `make help` that prints available targets and short descriptions.
- Wrap `uv sync` (or equivalent install) and the development server command behind stable target names (`sync`, `dev`).
- Use `uv run` in recipes so the locked environment is used consistently.

**Non-Goals:**

- Windows `nmake` or cross-platform task runners beyond POSIX Make (users on Windows can use Git Bash or document alternatives separately).
- CI integration or Docker in this change.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Help pattern | `help` as default goal, targets annotated with `## comment` for `awk`/grep self-documentation | Common idiom; no extra dependency. |
| Server command | `uv run uvicorn main:app --reload --host 0.0.0.0 --port $(PORT)` with `PORT` overridable | Matches README; one place to change flags. |
| Sync | `uv sync` | Aligns with existing README and lockfile workflow. |

**Alternatives considered:** `just` or `task` (rejected: user asked for Makefiles).

## Risks / Trade-offs

- **Make vs uv** — If `uv` is missing, recipes fail clearly → document prerequisite in README.

## Migration Plan

Not applicable. Add files only.

## Open Questions

- None.
