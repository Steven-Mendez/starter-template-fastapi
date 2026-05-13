## 1. uv cache

- [ ] 1.1 In `.github/workflows/ci.yml`, add `with: { enable-cache: true, cache-dependency-glob: "uv.lock" }` to every `astral-sh/setup-uv` step.

## 2. pre-commit job (gate)

- [ ] 2.1 Add a `pre-commit` job to `.github/workflows/ci.yml` that runs `uv run pre-commit run --all-files --hook-stage pre-commit`.
- [ ] 2.2 Cache `~/.cache/pre-commit` keyed by `${{ hashFiles('.pre-commit-config.yaml') }}`.
- [ ] 2.3 Add `needs: pre-commit` to the `quality`, `test`, `cov`, and `integration` jobs so downstream work runs only on pre-commit success.

## 3. Coverage artifact + optional Codecov

- [ ] 3.1 After the `make cov` step, add `actions/upload-artifact@<sha>` with `name: coverage` and `path: reports/coverage.*`.
- [ ] 3.2 Add a `codecov/codecov-action@<sha>` step with `if: ${{ secrets.CODECOV_TOKEN != '' }}` and `continue-on-error: true` — does not block CI when the token is unset or the service is degraded.

## 4. Makefile

- [ ] 4.1 Append `outbox-retry-failed` to the `.PHONY` declaration at the top of `Makefile`.

## 5. Verify

- [ ] 5.1 `make ci` green locally.
- [ ] 5.2 Open a dummy PR and confirm: `pre-commit` job runs first; downstream jobs wait on it; coverage artifact attaches to the run summary; missing `CODECOV_TOKEN` does not fail the workflow.
