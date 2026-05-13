## 1. Vulnerability alerts

- [ ] 1.1 Add to `renovate.json`:
  ```json
  "vulnerabilityAlerts": {
    "enabled": true,
    "labels": ["security"],
    "schedule": ["at any time"],
    "prCreation": "immediate",
    "automerge": true,
    "automergeType": "pr"
  }
  ```
- [ ] 1.2 Add a `packageRules` entry that disables auto-merge for `updateType: "major"` security bumps (human review required).

## 2. pre-commit manager

- [ ] 2.1 Add `"pre-commit": { "enabled": true }` to the top-level `renovate.json`.

## 3. Grouping rules

- [ ] 3.1 Confirm/add `packageRules` for `production-deps` (matches `dependencies` and `optional-dependencies`, weekly schedule, group name `production-deps`).
- [ ] 3.2 Confirm/add `packageRules` for `dev-deps` (matches `dependency-groups`/`dev`, weekly, group name `dev-deps`).
- [ ] 3.3 Confirm/add `packageRules` for `pre-commit-hooks` (matches the `pre-commit` manager, weekly, group name `pre-commit-hooks`).
- [ ] 3.4 Add `lockfileMaintenance: { "enabled": true, "schedule": ["before 9am on monday"] }`.

## 4. Verify

- [ ] 4.1 Run `npx --package renovate -- renovate-config-validator renovate.json` (or wait for the next Renovate self-validation run) and confirm the schema is accepted.
- [ ] 4.2 Update `docs/operations.md`: security PRs ignore the regular schedule and auto-merge for patch/minor on green CI; major bumps require human review.
