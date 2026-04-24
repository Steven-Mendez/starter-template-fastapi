## Context

Current behavior and tests are close to strict hexagonal boundaries, but remaining drift appears in three places: aggregate consistency operations, architecture test coverage breadth, and OpenSpec catalog integrity.

## Goals

- Ensure aggregate-level column deletion keeps stable contiguous positions.
- Remove cross-entity private-method coupling from domain aggregate operations.
- Make architecture tests detect bypasses even when annotations/import styles vary.
- Ensure OpenSpec catalog files remain structurally valid and placeholder-free.

## Decisions

### 1) Column removal and reindexing become explicit aggregate behavior
- Introduce/require a public aggregate operation that removes a column and normalizes remaining column positions.
- Command handlers call this explicit aggregate behavior instead of ad hoc list mutation plus `hasattr` fallback.

### 2) Domain aggregate avoids child private API calls
- Aggregate operations must not invoke child underscore/private methods.
- Child collections expose sufficient public behavior for required consistency updates.

### 3) Architecture tests move beyond annotation-only checks
- Add route-dependency graph validation (FastAPI dependant tree) to block container-provider injection bypasses.
- Expand import-governance checks to cover both `from x import y` and `import x as y` styles.

### 4) OpenSpec catalog hygiene is enforced as governance
- All maintained specs must include canonical `## Purpose` and `## Requirements` sections.
- Placeholder Purpose content (e.g., `TBD`) is disallowed in main specs.

## Risks

- Aggregate behavior refactor may affect ordering assumptions in tests.
- Stricter governance checks can fail existing pipelines until legacy specs are normalized.

## Mitigation

- Add focused unit tests for column position normalization after delete/move.
- Incrementally normalize invalid spec files in the same change scope.
