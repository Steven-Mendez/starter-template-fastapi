## Context

Python projects generate `__pycache__`, virtualenv directories, and tool caches; developers use `.env` for secrets. uv projects should commit `uv.lock` for apps.

## Goals / Non-Goals

**Goals:**

- Ignore generated Python artifacts, local venvs, coverage output, and `.env` files.
- Keep `uv.lock` and `.python-version` tracked.
- Use one root `.gitignore` (POSIX-oriented patterns).

**Non-Goals:**

- Per-OS exhaustive lists beyond common cases (macOS/Windows basics).
- Ignoring `.cursor/` (team rules may live there).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Env files | Ignore `.env`, `.env.*`, allow `!.env.example` | Secrets stay local; example template can be committed. |
| Lockfile | Not ignored | Reproducible installs per uv best practice. |

## Risks / Trade-offs

- **Over-ignore** — If a future legitimate file matches a pattern, adjust with negation rules.

## Migration Plan

Add `.gitignore`; no data migration.

## Open Questions

- None.
