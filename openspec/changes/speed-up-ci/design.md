## Context

Three CI ergonomics gaps: no uv cache, no coverage artifact publication, and pre-commit runs locally only. Each is small; together they save minutes per PR and remove silent local↔CI drift.

## Decisions

- **uv cache via `setup-uv`, not `actions/cache`**: the built-in cache is correctly invalidated on `uv.lock` changes; one less custom action to maintain.
- **Coverage as a workflow artifact**: reviewers can download `coverage.json` / `coverage.xml` and inspect uncovered files directly.
- **Codecov upload is OPTIONAL and conditional**: the `codecov/codecov-action` step runs only if `secrets.CODECOV_TOKEN` is set; CI does NOT block on Codecov availability or rate limits. Rationale: Codecov outages should not block PR merges; the artifact upload remains the source of truth for in-repo review.
- **pre-commit runs FIRST, as a gate**: a dedicated `pre-commit` job runs before `quality`, `test`, and `cov`; downstream jobs `needs: pre-commit`. Rationale: pre-commit is the fastest signal; if formatting or whitespace are wrong, fail in 30 seconds instead of waiting on the full matrix. Parallel-with-fan-out is also viable but a sequential gate gives the cleanest "red bar" signal and the cheapest cancellation.

## Non-goals

- Not migrating off GitHub Actions to another CI provider.
- Not parallelising tests beyond the existing job split (no pytest-xdist sharding).
- Not adopting a third-party cache action; `setup-uv`'s built-in cache is sufficient.
- Not adding self-hosted runners or `larger-runners` SKUs.
- Not gating PR merge on Codecov coverage delta — the upload is informational only.

## Risks / Trade-offs

- **Risk**: uv cache poisoning. Mitigation: keyed on `uv.lock`; manual purge is one-click in the Actions UI.
- **Risk**: pre-commit-as-gate adds latency to PRs whose downstream tests would have passed anyway. Mitigation: pre-commit job is <60s; the latency is a fair price for the cleaner failure mode.

## Migration

Single PR. Rollback: revert YAML.

## Depends on

- None.

## Conflicts with

- Shares `.github/workflows/ci.yml` with `harden-ci-security` — coordinate landing order to avoid YAML merge thrash.
- Shares `Makefile` `.PHONY` block with `add-worker-image-target`, `add-outbox-retention-prune`, `document-one-way-migration-policy` — section-level edits only.
