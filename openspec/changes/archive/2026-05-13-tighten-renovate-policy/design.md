## Context

Renovate's defaults batch all PRs through the same cadence. Security PRs should not wait; pre-commit hooks should track upstream the same way runtime deps do.

## Decisions

- **Vulnerability alerts on the fast lane.** `vulnerabilityAlerts.prCreation = immediate`; security PRs auto-merge for patch/minor when CI is green. Rationale: matches the threat model.
- **Pre-commit manager enabled.** `"pre-commit": { "enabled": true }`. Cost-free; one PR per hook bump.
- **Grouping rules (confirmed):**
  - **Security PRs** (`labels: ["security"]`): grouped by package, `automerge: true` for patch/minor on `vulnerabilityAlerts`-derived PRs once CI is green. Major-version security bumps require human review.
  - **Lockfile maintenance**: scheduled `["before 9am on monday"]`, weekly cadence, separate PR.
  - **Production deps** (`[project] dependencies` and `[project.optional-dependencies]`): grouped as `production-deps`, weekly schedule.
  - **Dev deps** (`[dependency-groups] dev`): grouped as `dev-deps`, weekly schedule.
  - **pre-commit hooks**: grouped as `pre-commit-hooks`, weekly schedule.

## Non-goals

- Not pinning every transitive dep — the `production-deps` and `dev-deps` groups still rely on `uv.lock` for transitive resolution.
- Not introducing per-package allow/deny lists beyond grouping.
- Not auto-merging major bumps under any condition (security or otherwise).
- Not migrating to Dependabot or a different bot.
- Not enabling automatic vulnerability ignore lists (`.trivyignore` aside, which is managed in `harden-ci-security`).

## Risks / Trade-offs

- Noisier inbox during the first week post-enable as the pre-commit manager catches up. Mitigation: grouping rules collapse hook bumps; drift is the worse alternative.
- Auto-merging security PRs assumes CI signal is trustworthy. Mitigation: `harden-ci-security` and `speed-up-ci` raise the bar (pre-commit gate + dependency-review + Trivy scan).

## Migration

Single PR. Rollback: revert JSON.

## Depends on

- None. Pairs with `speed-up-ci` (pre-commit-as-gate) and `harden-ci-security` (dependency-review + Trivy) for trustworthy auto-merge signal.

## Conflicts with

- Shares `renovate.json` with `harden-dockerfile` (Docker base-image pinning rules) — coordinate landing order.
