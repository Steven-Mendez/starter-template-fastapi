## 1. Top-level permissions

- [x] 1.1 Add `permissions: { contents: read }` at the workflow top of `ci.yml`. Individual jobs raise `permissions: { security-events: write }` for SARIF upload, etc.

## 2. SHA-pin all actions

- [x] 2.1 Inventory every `uses:` in `.github/workflows/ci.yml` (217 lines) and `.github/workflows/setup-repo.yml`; record the resolved commit SHA per action and version in the PR description.
- [x] 2.2 Replace `uses: org/action@<version>` with `uses: org/action@<commit-sha>  # v<version>` across `.github/workflows/ci.yml`.
- [x] 2.3 Do the same across `.github/workflows/setup-repo.yml`.
- [x] 2.4 Update `.github/renovate.json5` (see `tighten-renovate-policy`) so the `github-actions` manager bumps SHAs and keeps the `# v<version>` comment in sync.

## 3. Trivy image scan

- [x] 3.1 In the `docker` job (or a new `image-scan` job triggered after build):
  ```yaml
  - uses: aquasecurity/trivy-action@<sha>
    with: { image-ref: api:latest, severity: HIGH,CRITICAL, exit-code: 1 }
  ```
- [x] 3.2 Also scan the worker image once `add-worker-image-target` lands.

## 4. SBOM

- [x] 4.1 Add `anchore/sbom-action@<sha>` after the build step; output format `spdx-json`.
- [x] 4.2 `actions/upload-artifact` the SBOM file.

## 5. Dependency review

- [x] 5.1 Add a `dependency-review` job on `pull_request` events using `actions/dependency-review-action@<sha>`. Configure `fail-on-severity: high` (the action treats this as "high or higher", so `critical` is included). Add `comment-summary-in-pr: on-failure` so reviewers see the diff inline. Note: this job needs `pull-requests: write` permission only for the comment, not for the scan itself.

## 6. Wrap-up

- [x] 6.1 `make ci` (local) is unaffected.
- [x] 6.2 Verify PRs from a fork still pass (no missing-secret friction).
