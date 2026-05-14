## ADDED Requirements

### Requirement: CI scans the built container image and produces an SBOM

CI SHALL build the production image and run Trivy (or equivalent) with `severity=HIGH,CRITICAL` and `exit-code=1`. A SBOM (SPDX or CycloneDX JSON) SHALL be generated for the same image and uploaded as a workflow artifact. PRs SHALL also run `actions/dependency-review-action` with `fail-on-severity: high`.

The workflow SHALL declare `permissions: { contents: read }` at the top level; per-job elevations are explicit.

All `uses:` references SHALL be pinned by commit SHA (with a version comment).

#### Scenario: CRITICAL CVE in base image fails the build

- **GIVEN** a Trivy run that detects a CRITICAL vulnerability in the runtime image
- **WHEN** the job completes
- **THEN** the job exits non-zero and the PR check is failed

#### Scenario: PR adds a HIGH-severity dependency

- **GIVEN** a PR that introduces a transitive dep with a HIGH-severity advisory
- **WHEN** `dependency-review` runs
- **THEN** the check is failed with a clear message naming the dep

#### Scenario: A PR removes or skips the Trivy/SBOM gate

- **GIVEN** a PR that deletes the Trivy or SBOM step from `.github/workflows/ci.yml`, or sets `continue-on-error: true` on it
- **WHEN** CI runs on that PR
- **THEN** the workflow fails because the required `image-scan` / `sbom` job (or step output) is missing or did not enforce its exit code
- **AND** the failure message names the missing gate

#### Scenario: An unpinned action reference is rejected

- **GIVEN** a PR that adds `uses: org/action@v4` (tag) instead of a commit SHA
- **WHEN** CI runs
- **THEN** the workflow's pin-check step (or `dependency-review-action`'s action pinning policy) fails the build with the unpinned reference named in the log
