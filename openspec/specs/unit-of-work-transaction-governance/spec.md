# unit-of-work-transaction-governance Specification

## Purpose
TBD - created by archiving change hex-transaction-boundary-unification. Update Purpose after archive.
## Requirements
### Requirement: Single Transaction Owner for Command Operations
The system MUST enforce unit-of-work as the single owner of transaction lifecycle for all command-side state mutations.

#### Scenario: Successful command commits exactly once
- **WHEN** a command handler completes successfully inside a unit-of-work context
- **THEN** exactly one commit is executed by the unit-of-work and repositories do not issue independent commits

#### Scenario: Failed command rolls back atomic operation
- **WHEN** an exception occurs after one or more mutations in a command handler
- **THEN** the unit-of-work performs rollback and no partial mutation is persisted

### Requirement: Repository Command Behavior Under UoW
Repositories used by command handlers MUST be transaction-participant components and MUST NOT own commit/rollback decisions.

#### Scenario: Repository mutation does not finalize transaction
- **WHEN** a repository method persists a changed aggregate inside an active unit-of-work
- **THEN** the method returns without committing and leaves transaction finalization to the unit-of-work

#### Scenario: Repository failure propagates to UoW boundary
- **WHEN** a repository operation raises an infrastructure or concurrency exception
- **THEN** the exception propagates to the unit-of-work boundary where rollback and translation are applied

### Requirement: Transaction Contract Conformance Testing
The system MUST provide reusable contract tests validating command transaction semantics across all repository/unit-of-work adapter implementations.

#### Scenario: Adapter passes commit and rollback conformance suite
- **WHEN** a repository/UoW adapter pair is introduced or modified
- **THEN** it passes contract tests for commit-once, rollback-on-failure, and no-side-effects-after-abort behavior
