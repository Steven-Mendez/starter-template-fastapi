## Context

The CI pipeline already covers source-side hygiene (lint, types, tests, bandit, gitleaks, pip-audit). The missing pieces are *build artifact* hygiene (container scan, SBOM) and *PR-time* hygiene (dep review).

## Decisions

- **Fail on HIGH/CRITICAL only**: anything less aggressive becomes noise; anything more aggressive makes the gate too strict for routine dev.
- **SHA-pin actions**: every GitHub Actions security advisory in the last two years involves an unpinned action getting compromised. The fix is a one-time refactor + Renovate.
- **Scan both runtime images**: once `add-worker-image-target` lands, the Trivy job builds and scans `--target runtime` (API) and `--target runtime-worker` (worker) in parallel matrix entries.

## Non-goals

- Not signing images (cosign / Sigstore) in this change; that is a separate proposal.
- Not adding runtime/admission-time scanning (Kyverno, Trivy operator) — CI-time only.
- Not changing the base image or `Dockerfile` — covered by `harden-dockerfile`.
- Not failing on MEDIUM/LOW Trivy findings; only `HIGH,CRITICAL` per the decision below.
- Not introducing a new secret scanner; the existing `gitleaks` step stays.

## Risks / Trade-offs

- **Risk**: false-positive vulnerability with no upstream fix. Mitigation: Trivy supports inline `.trivyignore` for documented exceptions.
- **Trade-off**: +1–3 minutes PR latency. Acceptable for the coverage gained.

## Depends on

- `add-worker-image-target` — the worker-image scan matrix entry is only meaningful once the `runtime-worker` stage exists.
- `harden-dockerfile` — digest-pinned base images materially reduce Trivy's noise floor.

## Conflicts with

- `.github/workflows/ci.yml` is shared with `speed-up-ci`. The two changes touch different jobs but the workflow `permissions:` block and the SHA-pinning of `actions/checkout` / `actions/setup-python` overlap.
- `pyproject.toml` is shared with `enable-strict-mypy`, `expand-ruff-ruleset`, `trim-runtime-deps`, `add-error-reporting-seam`, `clean-architecture-seams`. No direct line collision (this change only adds CI YAML), but coordinated merges keep diffs small.

## Migration

Single PR. Rollback: revert YAML.
