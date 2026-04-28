# Proposal: Aggregate Encapsulation Phase 2

**Change ID**: `2026-04-27-aggregate-encapsulation-phase2`
**Priority**: Medium
**Status**: Proposed

---

## Problem Statement

Initial encapsulation was added for board column insertion, but other mutation flows still rely on traversing and mutating aggregate internals directly from handlers.

This keeps domain invariants dependent on orchestration discipline rather than explicit aggregate intent APIs.

## Scope

In scope:
- Introduce additional aggregate/domain intent methods for common mutation operations.
- Refactor command handlers to use those methods.
- Add tests that lock intent-method usage and invariant-preserving behavior.

Out of scope:
- Full value-object migration.
- Cross-bounded-context redesign.

## Acceptance Targets

1. Handlers avoid direct list/field mutation for targeted operations.
2. Domain methods represent mutation intent clearly.
3. Existing behavior remains stable under current tests.
