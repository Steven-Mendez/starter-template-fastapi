## Why

`pyproject.toml:137-144` enables only four mypy flags (`warn_unused_configs`, `disallow_untyped_defs`, `check_untyped_defs`, `no_implicit_optional`). Missing: `strict`, `warn_return_any`, `warn_unused_ignores`, `warn_redundant_casts`, `strict_equality`, `disallow_any_generics`, `disallow_untyped_decorators`, `no_implicit_reexport`. The codebase has scattered `# type: ignore` and `cast(Any, ...)` that strict mode would flag.

## What Changes

- Set `strict = true` in `[tool.mypy]` (single switch).
- Sweep `# type: ignore` and `cast(Any, ...)` across `src/`; remove the ones no longer needed; annotate the remainder with an inline reason and an `XXX` follow-up task.
- Add per-module `ignore_missing_imports` overrides only for genuinely untyped third-party packages (e.g. `arq` if its stubs lag); each gets a one-line comment.

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: `pyproject.toml` (one new line under `[tool.mypy]`), plus type-annotation cleanups across `src/` (estimate ~20-30 files).
- **CI**: `make typecheck` becomes a stricter gate; one-time pain to land, ongoing safety.
- **Backwards compatibility**: none — CI-gate change only.
