## Why

Two Renovate-config gaps:

1. **No `vulnerabilityAlerts` fast lane.** Security PRs currently batch into the normal cadence with `prHourlyLimit` and grouping rules. A vulnerable transitive dep waits days for a normal-priority bump.
2. **`pre-commit` manager is disabled by default.** `.pre-commit-config.yaml` pins hook versions but Renovate will not bump them; drift accumulates.

## What Changes

- Add a `vulnerabilityAlerts` block to `renovate.json`: `{ "enabled": true, "labels": ["security"], "schedule": ["at any time"], "prCreation": "immediate", "automerge": true, "automergeType": "pr" }` — auto-merge security patch/minor when CI is green; major-version security bumps fall through to human review via `packageRules` matching `updateType: "major"`.
- Enable the `pre-commit` manager: `"pre-commit": { "enabled": true }`.
- Confirm and document existing/added `packageRules` groupings:
  - `production-deps` (weekly): `[project] dependencies` and `[project.optional-dependencies]`.
  - `dev-deps` (weekly): `[dependency-groups] dev`.
  - `pre-commit-hooks` (weekly): hooks pinned in `.pre-commit-config.yaml`.
  - `lockfileMaintenance` (`schedule: ["before 9am on monday"]`).

**Capabilities — Modified**: `quality-automation`.

## Impact

- **Code**: `renovate.json` only.
- **Docs**: `docs/operations.md` gains a short note that security PRs ignore the regular schedule and auto-merge for patch/minor when CI is green.
- **Operations**: security bumps land within hours; pre-commit hooks stay current; weekly lockfile churn lands in a single window.
