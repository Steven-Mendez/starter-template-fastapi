# Spec: Persistence Concurrency and Constraints

**Capability**: persistence-concurrency
**Change**: 2026-04-27-persistence-concurrency-constraints

---

## ADDED Requirements

### Requirement: PCC-01 — Aggregate writes detect concurrency conflicts

**Priority**: High

The persistence layer MUST detect stale aggregate writes and reject them with a deterministic conflict outcome.

**Acceptance Criteria**:
1. A version/concurrency marker exists for persisted board aggregate state.
2. Repository save detects stale version writes.
3. Stale writes return/raise a conflict outcome instead of silently overwriting.

#### Scenario: Stale update is rejected

- Given: two writers load the same board version
- When: writer A commits and writer B commits stale state
- Then: writer B receives a conflict outcome

### Requirement: PCC-02 — Ordering and position constraints are enforced at DB level

**Priority**: High

The DB schema MUST enforce ordering uniqueness and non-negative positions.

**Acceptance Criteria**:
1. `(board_id, position)` is unique for columns.
2. `(column_id, position)` is unique for cards.
3. Position values cannot be negative.

#### Scenario: Duplicate card position in a column fails

- Given: two cards in same column with identical position
- When: persistence write is attempted
- Then: DB rejects the write
