# Spec: Aggregate Encapsulation Phase 2

**Capability**: aggregate-encapsulation-phase2
**Change**: 2026-04-27-aggregate-encapsulation-phase2

---

## ADDED Requirements

### Requirement: AEP2-01 — Command handlers use explicit domain mutation intents

**Priority**: High

Command handlers MUST call domain methods for targeted mutations instead of manipulating aggregate internals directly.

**Acceptance Criteria**:
1. Targeted handler mutation flows are implemented via domain intent methods.
2. Direct list mutations in handlers are removed for scoped flows.
3. Existing command behavior remains unchanged from API perspective.

#### Scenario: Handler applies card update through domain method

- Given: a patch command for a card
- When: the handler executes
- Then: the update is delegated to a domain intent method

### Requirement: AEP2-02 — Traversal and mutation duplication is reduced

**Priority**: Medium

Repeated aggregate traversal logic for mutation should be centralized into domain/helper intent APIs where reasonable.

**Acceptance Criteria**:
1. At least one duplicated traversal/mutation pattern is centralized.
2. Domain tests cover centralized behavior.

#### Scenario: Shared domain helper handles repeated card lookup mutation

- Given: two handler paths requiring card mutation lookup
- When: updates are implemented
- Then: they rely on shared domain intent/helper behavior
