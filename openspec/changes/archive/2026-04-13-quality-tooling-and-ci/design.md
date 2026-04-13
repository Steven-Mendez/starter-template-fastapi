## Context

The repository already uses `uv`, a lockfile, and a small FastAPI service, but quality checks are mostly manual. Existing OpenSpec capabilities define development commands, yet there is no CI enforcement layer and no explicit policy for lint/type tools in `pyproject.toml`.

## Goals / Non-Goals

**Goals:**
- Establish a deterministic quality baseline for local and CI workflows.
- Ensure contributors can run the same checks locally through `Makefile` targets.
- Keep checks fast enough for routine pull request feedback.

**Non-Goals:**
- Introduce broad code-style churn unrelated to safety or maintainability.
- Add end-to-end deployment workflows in this change.
- Replace `uv` with a different package manager.

## Decisions

- Use Ruff as the primary linter and formatter surface because it is fast and can run in both local and CI contexts with minimal configuration overhead.
- Use mypy for static typing checks with pragmatic strictness to avoid blocking incremental adoption.
- Add a GitHub Actions workflow for `lint`, `typecheck`, and `pytest -m "not e2e"` on pull requests; keep e2e in a separate flow or local contract run.
- Keep `Makefile` as the single entrypoint for developer commands so docs and CI remain aligned.
- Enforce dependency separation by keeping runtime packages in `project.dependencies` and test/tooling in dev groups.

## Risks / Trade-offs

- [CI duration increases] -> Keep default PR suite to unit/integration checks and defer expensive e2e runs.
- [Type-checking friction on legacy code] -> Start with a scoped mypy config and tighten gradually.
- [Formatter/linter rule disagreements] -> Pin explicit rules in `pyproject.toml` and document exceptions.
