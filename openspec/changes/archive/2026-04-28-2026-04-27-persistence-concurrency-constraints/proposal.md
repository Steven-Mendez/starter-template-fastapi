# Proposal: Persistence Concurrency and Constraints

**Change ID**: `2026-04-27-persistence-concurrency-constraints`
**Priority**: High
**Status**: Proposed

---

## Problem Statement

The current persistence model allows lost updates and weak ordering/data-integrity guarantees:

- no optimistic concurrency/version field on aggregates
- no DB uniqueness constraints for ordered positions
- no DB-level non-negative checks for position fields

These gaps can produce invalid ordering states and silent overwrites under concurrent writes.

## Scope

In scope:
- Add optimistic locking strategy for board aggregate writes.
- Add DB constraints for ordering and basic position validity.
- Update repository persistence logic and tests to enforce these rules.

Out of scope:
- Full event sourcing or distributed locking.
- Cross-service transaction orchestration.

## Acceptance Targets

1. Concurrent conflicting writes are detected and surfaced deterministically.
2. DB schema prevents duplicate positions within a board/column scope.
3. DB schema rejects negative positions.
