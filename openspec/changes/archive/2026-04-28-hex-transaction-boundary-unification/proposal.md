## Why

Current transaction ownership is split between unit-of-work and repository execution paths, creating ambiguity and potential inconsistency in commit/rollback behavior. Hexagonal architecture requires a clear application-level transaction boundary so business operations have deterministic atomicity.

## What Changes

- Establish a single authoritative transaction owner for command flows.
- Define mandatory repository behavior inside and outside a unit-of-work context.
- Add explicit requirements for commit, rollback, and exception semantics.
- Define compatibility policy for adapters that currently self-commit.
- **BREAKING**: repository implementations that perform implicit commits in command paths will be non-compliant.

## Capabilities

### New Capabilities
- `unit-of-work-transaction-governance`: Define normative transaction ownership and lifecycle semantics for command execution.

### Modified Capabilities
- None.

## Impact

- Affected code: unit-of-work adapters, command repositories, and command handlers.
- Affected systems: integration tests and any scripts relying on side effects from implicit repository commits.
- Potential operational impact: fewer partial writes and clearer rollback behavior under failure.
