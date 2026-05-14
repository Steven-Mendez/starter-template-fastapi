## Why

Three CI ergonomics gaps:

1. **`setup-uv` runs without caching.** `enable-cache: true` + `cache-dependency-glob: uv.lock` is free wheel caching across runs and shaves ~30s/job.
2. **`make cov` produces `reports/coverage.json` and `coverage.xml` but nothing publishes them.** No artifact upload, no Codecov integration — coverage regressions on PRs are invisible to reviewers.
3. **`pre-commit` is configured locally but never run in CI.** A contributor without hooks installed can land formatting/whitespace drift that the hooks would have caught.

Plus: `Makefile`'s `.PHONY` list is missing `outbox-retry-failed` (silent no-op if a file of that name ever lands).

## What Changes

- Add `with: { enable-cache: true, cache-dependency-glob: "uv.lock" }` to every `astral-sh/setup-uv` step in `.github/workflows/ci.yml`.
- Add `actions/upload-artifact` for `reports/coverage.json` and `reports/coverage.xml` after `make cov`.
- Add a dedicated `pre-commit` CI job that runs FIRST; subsequent jobs (`quality`, `test`, `cov`, `integration`) `needs: pre-commit`. Cache `~/.cache/pre-commit` keyed by `.pre-commit-config.yaml`.
- Codecov upload is OPTIONAL: the step uses `if: ${{ secrets.CODECOV_TOKEN != '' }}` and `continue-on-error: true` so CI does not block when the token is unset or Codecov is degraded.
- Append `outbox-retry-failed` to the `Makefile` `.PHONY` list.

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: `.github/workflows/ci.yml`, `Makefile`.
- **CI**: faster runs after the first cache-warm; coverage artifacts visible on PRs; pre-commit drift caught early.
- **Production**: none.
