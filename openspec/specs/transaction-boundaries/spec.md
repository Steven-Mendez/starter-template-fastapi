# transaction-boundaries Specification

## Purpose
Define clear transaction ownership between repositories and Unit of Work so command paths have predictable commit/rollback semantics.

## Requirements

### Requirement: TXB-01 — UoW-backed command paths have a single transaction owner

**Priority**: High

For command flows that execute through `UnitOfWorkPort`, transaction ownership MUST be centralized in the Unit of Work, not in repository base methods.

**Acceptance Criteria**:
1. `SessionSQLModelKanbanRepository.save` does not commit implicitly when used via `SqlModelUnitOfWork`.
2. `SessionSQLModelKanbanRepository.remove` does not commit implicitly when used via `SqlModelUnitOfWork`.
3. Command handlers continue to persist changes only when `uow.commit()` is called.

#### Scenario: Save in UoW scope without commit does not persist

- Given: a board loaded and modified in `with SqlModelUnitOfWork(...) as uow`
- When: `uow.kanban.save(board)` is called and the scope exits without `uow.commit()`
- Then: the persisted board state remains unchanged

#### Scenario: Remove in UoW scope without commit does not persist

- Given: an existing persisted board
- When: `uow.kanban.remove(board_id)` is called and the scope exits without `uow.commit()`
- Then: the board still exists in storage

### Requirement: TXB-02 — Unit of Work exit semantics explicitly rollback non-committed work

**Priority**: High

`SqlModelUnitOfWork.__exit__` MUST rollback pending transactional work before session close whenever the scope exits with an open transaction.

**Acceptance Criteria**:
1. On exceptional exit, `SqlModelUnitOfWork` executes rollback before close.
2. On normal exit without `commit()`, `SqlModelUnitOfWork` executes rollback before close.
3. On normal exit after `commit()`, persisted data remains durable and no uncommitted writes leak across sessions.

#### Scenario: Exception inside UoW rolls back pending writes

- Given: a new board saved inside `with SqlModelUnitOfWork(...) as uow`
- When: an exception is raised before `uow.commit()`
- Then: no new board is persisted after the scope exits

### Requirement: TXB-03 — Shared repository base logic contains no hidden commit semantics

**Priority**: Medium

The shared `_BaseSQLModelKanbanRepository` write operations MUST not embed commit calls or commit hooks. Commit policy MUST be delegated to concrete adapters.

**Acceptance Criteria**:
1. `_BaseSQLModelKanbanRepository.save` contains no commit call.
2. `_BaseSQLModelKanbanRepository.remove` contains no commit call.
3. Standalone `SQLModelKanbanRepository` remains functional for direct adapter usage by committing in adapter-specific write-session handling.

#### Scenario: Standalone repository save remains durable

- Given: a `SQLModelKanbanRepository` instance used directly
- When: `repository.save(board)` is called
- Then: a second repository instance can read that board from storage
