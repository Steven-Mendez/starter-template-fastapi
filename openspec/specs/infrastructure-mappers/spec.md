# infrastructure-mappers Specification

## Purpose
TBD - created by archiving change infrastructure-mapper-module. Update Purpose after archive.
## Requirements
### Requirement: IM-03 — `_to_card_read` static method does not exist on `_BaseSQLModelKanbanRepository`

The system MUST satisfy this requirement as specified below.

**Priority**: Low

The `_to_card_read` static helper is an ad-hoc inline mapper on the repository class. After this change it is replaced by `card_table_to_domain` in the mapper module.

**Acceptance Criteria**:
1. `_BaseSQLModelKanbanRepository` has no `_to_card_read` method.
2. `rg "_to_card_read" src/infrastructure/` produces zero results.
3. Card mapping uses `card_table_to_domain` from `src.infrastructure.persistence.sqlmodel.mappers`.

#### Scenario: Card mapping through mapper function

- Given: `src/infrastructure/persistence/sqlmodel_repository.py`
- When: the source is inspected for `_to_card_read`
- Then: no reference appears

