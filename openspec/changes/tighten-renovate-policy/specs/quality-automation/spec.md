## ADDED Requirements

### Requirement: Renovate fast-tracks security alerts and tracks pre-commit hooks

`renovate.json` SHALL include a `vulnerabilityAlerts` block enabling immediate PR creation for security advisories with `automerge: true` for non-major bumps. It SHALL enable the `pre-commit` manager so hook versions in `.pre-commit-config.yaml` are tracked. It SHALL define grouping rules for production deps, dev deps, and pre-commit hooks, plus a weekly Monday `lockfileMaintenance` schedule.

#### Scenario: Security advisory produces an immediate PR

- **GIVEN** a transitive dep gains a HIGH-severity advisory
- **WHEN** Renovate next polls (or via the alert webhook)
- **THEN** a PR is opened with label `security` and the rate limits / regular grouping rules do not delay it
- **AND** the PR is set to auto-merge if it is a patch or minor bump and CI is green

#### Scenario: Major-version security bump requires human review

- **GIVEN** a security advisory whose fix is a major-version bump
- **WHEN** Renovate opens the PR
- **THEN** the PR is labelled `security` but `automerge` is false
- **AND** the PR sits open until a maintainer approves it

#### Scenario: pre-commit hook bump produces a grouped PR

- **GIVEN** `pre-commit-hooks v6.1.0` is released
- **WHEN** Renovate's next weekly run executes
- **THEN** a PR is opened to bump the hook in `.pre-commit-config.yaml`
- **AND** the PR is part of the `pre-commit-hooks` group

#### Scenario: Weekly Monday lockfile maintenance lands in one window

- **GIVEN** the calendar reaches Monday 09:00 UTC
- **WHEN** Renovate runs
- **THEN** at most one lockfile-maintenance PR is open at any time and it lands within that window
