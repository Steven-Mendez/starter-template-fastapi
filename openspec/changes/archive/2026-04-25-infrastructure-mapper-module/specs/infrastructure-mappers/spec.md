# Spec: Infrastructure Mapper Module

**Capability**: infrastructure-mappers
**Change**: infrastructure-mapper-module

---

## ADDED Requirements

### Requirement: IM-01 — Dedicated mapper module exists at `src/infrastructure/persistence/sqlmodel/mappers.py`

The system MUST satisfy this requirement as specified below.


**Priority**: Medium

All ORM-to-domain and domain-to-ORM translation functions live in a single dedicated module. No inline entity construction exists inside the repository class methods.

**Acceptance Criteria**:
1. `src/infrastructure/persistence/sqlmodel/mappers.py` exists.
2. It contains at minimum: `card_table_to_domain`, `column_table_to_domain`, `board_table_to_domain`, `board_table_to_summary`, `card_domain_to_table`, `column_domain_to_table`.
3. Each function is a pure function: given input data, it returns a domain or ORM object with no side effects.
4. Mapper functions are importable without constructing a database session.

#### Scenario: Mapper functions importable in isolation

- Given: a Python interpreter with the project installed
- When: `from src.infrastructure.persistence.sqlmodel.mappers import card_table_to_domain` is executed
- Then: the import succeeds without connecting to a database

### Requirement: IM-04 — Mapper functions are unit-testable in isolation

The system MUST satisfy this requirement as specified below.


**Priority**: Low

Mapper functions can be unit-tested by passing ORM model instances and asserting domain object fields, without any session or database.

**Acceptance Criteria**:
1. `tests/unit/test_infrastructure_mappers.py` exists.
2. It contains at least three test functions covering `card_table_to_domain`, `board_table_to_summary`, and `card_domain_to_table`.
3. No test in that file requires a database connection or SQLAlchemy session.

#### Scenario: `card_table_to_domain` maps all fields correctly

- Given: a `CardTable` instance with known field values (`id`, `column_id`, `title`, `description`, `position`, `priority="high"`, `due_at=None`)
- When: `card_table_to_domain(card_table_instance)` is called
- Then: the returned `Card` has matching `id`, `column_id`, `title`, `description`, `position`, and `priority == CardPriority.HIGH`

#### Scenario: `card_table_to_domain` normalizes naive datetimes to UTC

- Given: a `CardTable` with `due_at` set to a naive `datetime` object (no timezone info)
- When: `card_table_to_domain(card_table_instance)` is called
- Then: the returned `Card.due_at` has `tzinfo` set to UTC

## ADDED Requirements

### Requirement: IM-02 — `SQLModelKanbanRepository` methods contain no inline domain or ORM object construction


**Priority**: Medium

`sqlmodel_repository.py` MUST not contain inline `Card(id=...)`, `Column(id=...)`, `Board(id=...)`, `CardTable(id=...)`, or `ColumnTable(id=...)` constructors. All such construction is delegated to mapper functions.

**Acceptance Criteria**:
1. `rg "Card\(id=" src/infrastructure/persistence/sqlmodel_repository.py` produces zero results.
2. `rg "Column\(id=" src/infrastructure/persistence/sqlmodel_repository.py` produces zero results.
3. `rg "Board\(id=" src/infrastructure/persistence/sqlmodel_repository.py` produces zero results.
4. `rg "CardTable\(id=" src/infrastructure/persistence/sqlmodel_repository.py` produces zero results.

#### Scenario: Repository `find_by_id` delegates to mapper

- Given: `SQLModelKanbanRepository.find_by_id` source code
- When: its body is inspected
- Then: it calls `board_table_to_domain(board_row, columns=...)` rather than constructing `Board(...)` inline

## ADDED Requirements

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
