## Why

CI runs bandit, pip-audit, gitleaks (good), but the built `runtime` image is never scanned (Trivy/Grype), no SBOM is published, no `dependency-review-action` runs on PRs, and there's no top-level `permissions:` block — workflows inherit `GITHUB_TOKEN` with broad write scope.

## What Changes

- Add a Trivy scan step in the `docker` job (or a new `image-scan` job). Fail the build on `HIGH` / `CRITICAL`.
- Add an `anchore/sbom-action` step uploading SPDX/CycloneDX as a workflow artifact.
- Add a `dependency-review` job on `pull_request` using `actions/dependency-review-action@<sha>`.
- Add top-level `permissions: { contents: read }` (jobs that need more raise their own permissions).
- Pin all `uses:` references by SHA (not `@v4`).

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: `.github/workflows/ci.yml`, possibly a new `image-scan.yml`.
- **CI runtime**: +1–3 minutes per PR (scanning is fast on a freshly built image).
- **Production**: catches vulnerable deps and OS packages before merge.
