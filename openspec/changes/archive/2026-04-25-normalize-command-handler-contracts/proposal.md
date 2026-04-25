# Proposal: Normalize Command Handler Contracts and Result Types

**Change ID**: `normalize-command-handler-contracts`
**Priority**: Medium
**Status**: Proposed
**Depends on**: `aggregate-repository-and-infrastructure-ports`

---

## Problem Statement

`KanbanCommandInputPort` has an inconsistent return type surface:

```python
class KanbanCommandInputPort(Protocol):
    def handle_create_board(self, command: CreateBoardCommand) -> AppBoardSummary:  # ← no error case
    def handle_patch_board(...) -> AppResult[AppBoardSummary, ApplicationError]:
    def handle_delete_board(...) -> AppResult[None, ApplicationError]:
    def handle_create_column(...) -> AppResult[AppColumn, ApplicationError]:
    def handle_delete_column(...) -> AppResult[None, ApplicationError]:
    def handle_create_card(...) -> AppResult[AppCard, ApplicationError]:
    def handle_patch_card(...) -> AppResult[AppCard, ApplicationError]:
```

`handle_create_board` is the only command that returns a value type directly rather than `AppResult`. This causes two concrete problems:

1. **Inconsistency in the port contract.** Callers of `KanbanCommandInputPort` must special-case `handle_create_board` — it cannot be matched with the same `case AppOk(value) / case AppErr(err)` pattern used for every other command. This creates a cognitive discontinuity.

2. **No error propagation path.** After `aggregate-repository-and-infrastructure-ports`, `handle_create_board` will call `uow.kanban.save(board)` which returns `Result[None, KanbanError]`. If `save` fails, the handler currently has no way to propagate that error to the caller — it would have to raise an exception, breaking the Result-pattern contract.

Additionally, the router in `src/api/routers/boards.py` handles `create_board` as a direct return:
```python
def create_board(body, commands):
    return to_board_summary_response(
        commands.handle_create_board(CreateBoardCommand(...))
    )
```
This would need to be updated to pattern-match on `AppResult` after normalization.

---

## Rationale

- **Uniform error handling**: every command in the port returns `AppResult`. Callers use the same pattern everywhere. This is easier to understand and less error-prone.
- **Error propagation consistency**: `handle_create_board` can now return `AppErr` for domain-level failures (e.g., business rule violations if introduced later). Infrastructure failures (DB errors) still become 500s via the exception handler — they are not surfaced as `AppErr`.
- **Simpler router code**: the router uses a `match` statement. Having one command that requires different handling breaks the visual uniformity of route handlers.
- **Note on `save()` infallibility**: `save()` does not return a Result — it is infallible. The `AppResult` return type on `handle_create_board` exists for consistency, not because `save` can fail. See ADR-1 in `aggregate-repository-and-infrastructure-ports/design.md`.

---

## Scope

**In scope:**
- Change `handle_create_board` return type in `KanbanCommandInputPort` from `AppBoardSummary` to `AppResult[AppBoardSummary, ApplicationError]`.
- Update `KanbanCommandHandlers.handle_create_board` implementation to return `AppOk(...)` or `AppErr(...)`.
- Update `src/api/routers/boards.py` `create_board` endpoint to pattern-match on `AppResult`.
- Update any tests that assert a bare `AppBoardSummary` return value from `handle_create_board`.

**Out of scope:**
- Changing any other command return types (already correct).
- Adding new error cases beyond what the repository produces.

---

## Affected Modules

| File | Change |
|---|---|
| `src/application/commands/port.py` | Modified — `handle_create_board` return type |
| `src/application/commands/handlers.py` | Modified — return `AppOk`/`AppErr` |
| `src/api/routers/boards.py` | Modified — pattern-match on `AppResult` |
| `tests/unit/test_kanban_command_handlers.py` | Modified — assert `AppOk(value)` |
| `tests/unit/test_kanban_cqrs.py` | Modified if affected |
| `tests/integration/test_kanban_api.py` | Likely unaffected (tests HTTP layer) |

---

## Proposed Change

Port:
```python
class KanbanCommandInputPort(Protocol):
    def handle_create_board(
        self, command: CreateBoardCommand
    ) -> AppResult[AppBoardSummary, ApplicationError]: ...
```

Handler (after `aggregate-repository-and-infrastructure-ports` is applied):
```python
def handle_create_board(
    self, command: CreateBoardCommand
) -> AppResult[AppBoardSummary, ApplicationError]:
    board = Board(
        id=self.id_gen.next_id(),
        title=command.title,
        created_at=self.clock.now(),
    )
    with self.uow:
        self.uow.kanban.save(board)   # infallible — see ADR-1 in aggregate-repository design.md
        self.uow.commit()
        return AppOk(AppBoardSummary(
            id=board.id,
            title=board.title,
            created_at=board.created_at,
        ))
```

Router (`BoardSummary` below is the **API schema** from `src.api.schemas.kanban`, not the domain model):
```python
@boards_router.post("/boards", response_model=BoardSummary, status_code=status.HTTP_201_CREATED)
def create_board(body: BoardCreate, commands: CommandHandlersDep) -> BoardSummary:
    match commands.handle_create_board(CreateBoardCommand(title=to_create_board_input(body))):
        case AppOk(value):
            return to_board_summary_response(value)
        case AppErr(err):
            raise_http_from_application_error(err)
```

---

## Acceptance Criteria

1. `KanbanCommandInputPort.handle_create_board` return type is `AppResult[AppBoardSummary, ApplicationError]`.
2. `KanbanCommandHandlers.handle_create_board` returns `AppOk(summary)` on success and `AppErr(error)` on failure.
3. `src/api/routers/boards.py` `create_board` uses a `match` statement, consistent with all other write endpoints.
4. All unit tests for `handle_create_board` assert `isinstance(result, AppOk)`.
5. All integration tests for `POST /boards` continue to return HTTP 201 on success.

---

## Migration Strategy

This change depends on `aggregate-repository-and-infrastructure-ports` because the new handler implementation calls `save(board)` which can return an error. Complete that change first, then apply this one in a single commit that touches port, handler, and router together.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Router change for `create_board` might introduce a missing return path warning | Use `NoReturn` hint on `raise_http_from_application_error` (already in place) to let type checker see both branches are covered. |
| Existing test code asserts bare `AppBoardSummary` return | Update tests to `assert isinstance(result, AppOk); assert result.value == ...`. |
