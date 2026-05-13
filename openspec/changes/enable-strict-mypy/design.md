## Context

`pyproject.toml:137` currently enables only four mypy flags. `strict = true` is the correct end state for any new codebase; partial strictness is a tri-state that rots into ambiguous per-file overrides nobody maintains.

## Decisions

- **One PR, single switch in `pyproject.toml`.** Set `strict = true`. Rationale: strict mode is tri-state — partial strictness creates ambiguous per-file overrides that rot. The codebase is small enough today that even ~hundreds of new errors are tractable in one review pass.
- **No per-file `disallow_any_explicit = false` overrides.** Any exception MUST be an inline `# type: ignore[<code>] # XXX: <reason>` with a matching `XXX` task line in `tasks.md`. Rationale: per-file overrides hide; inline ignores are visible at the call site.
- **Per-module `ignore_missing_imports` is allowed** only for genuinely untyped third-party packages (e.g. `arq` if its stubs lag). Each one gets a one-line comment naming the package.

## Non-goals

- Not introducing per-file `disallow_any_explicit = false` overrides.
- Not removing every `# type: ignore` in `src/` (some get an `XXX:` reason and ship as follow-ups).
- Not adding new third-party stub packages beyond what `dev` already lists (`types-cachetools`, `boto3-stubs[s3]`); other gaps get `ignore_missing_imports` overrides with a comment.
- Not authoring the strategic-`Any` cleanup itself — that ships in `type-cleanup-strategic-anys`.

## Risks / Trade-offs

- **Risk**: hidden type bugs surface and block in-flight work. Acceptable — that's the value.
- **Risk**: large diff in one PR. Mitigation: 70%+ of fixes are trivial annotation additions; review one feature at a time.

## Migration

Single PR. Rollback: revert the `pyproject.toml` change (the type cleanups can stay; they don't depend on strict mode).

## Depends on

- None.

## Conflicts with

- Shares `pyproject.toml` with `expand-ruff-ruleset`, `trim-runtime-deps`, `harden-ci-security`, `add-error-reporting-seam`, `clean-architecture-seams` — coordinate landing order to avoid merge thrash on the `[tool.*]` sections.

## Enables

- `type-cleanup-strategic-anys` (lands after this so its `# type: ignore` removals are actually flagged by mypy).
