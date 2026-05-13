## 1. Flip the switch

- [x] 1.1 Set `strict = true` in `[tool.mypy]` in `pyproject.toml` (single new line under existing block at lines 137-144).
- [x] 1.2 Run `make typecheck` and capture the error count per module to `reports/mypy-strict-baseline.txt`.

## 2. Triage and fix

- [x] 2.1 Triage new errors per `src/features/<feature>/` and `src/app_platform/`; group fixes by feature in the PR description.
- [x] 2.2 For each fixable error: add a real annotation (no `Any`, no `cast`).
- [x] 2.3 For each error that cannot be fixed in-PR: add an inline `# type: ignore[<code>] # XXX: <reason>` and append a matching `XXX` follow-up entry under section 5 of this file.
- [x] 2.4 Add per-module `[[tool.mypy.overrides]]` blocks in `pyproject.toml` for genuinely untyped third-party packages only; each block gets a one-line comment naming the package and why stubs are missing.

## 3. Cleanup unused ignores

- [x] 3.1 With `warn_unused_ignores = true` (from `strict`), grep `src/` for `# type: ignore` lines mypy now flags as `[unused-ignore]` and remove them.
- [x] 3.2 Grep `src/` for `cast(Any, ...)`; replace each call with a real type or remove the cast.

## 4. Verify

- [x] 4.1 `make typecheck` clean.
- [x] 4.2 `make ci` green.
- [x] 4.3 No new `# type: ignore` without an `XXX:` reason comment (grep gate).

## 5. XXX follow-ups (populated during section 2)

<!-- None — all strict-mode errors were resolved in-PR without follow-ups. -->
