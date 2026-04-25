# Tasks: Normalize Command Handler Contracts and Result Types

**Change ID**: `normalize-command-handler-contracts`
**Depends on**: `aggregate-repository-and-infrastructure-ports`

---

## Implementation Checklist

### Phase 1 — Update port definition

- [ ] In `src/application/commands/port.py`, change `handle_create_board` return type from `AppBoardSummary` to `AppResult[AppBoardSummary, ApplicationError]`.
- [ ] Ensure `AppOk`, `AppErr`, `AppResult` are imported in `port.py`.

### Phase 2 — Update handler implementation

- [ ] In `src/application/commands/handlers.py`, update `handle_create_board` to return `AppOk(summary)` on success.
- [ ] If `save(board)` returns `Err`, return `AppErr(from_domain_error(save_result.error))`.
- [ ] Verify return type annotation on the method matches `AppResult[AppBoardSummary, ApplicationError]`.

### Phase 3 — Update the router

- [ ] In `src/api/routers/boards.py`, update `create_board` endpoint to use a `match` statement:
  ```python
  match commands.handle_create_board(...):
      case AppOk(value):
          return to_board_summary_response(value)
      case AppErr(err):
          raise_http_from_application_error(err)
  ```
- [ ] Remove the existing direct `return to_board_summary_response(commands.handle_create_board(...))` call.
- [ ] Import `AppOk`, `AppErr` in `boards.py` if not already present.

### Phase 4 — Update tests

- [ ] In `tests/unit/test_kanban_command_handlers.py`, update any test that calls `handle_create_board` directly:
  - Before: `result = commands.handle_create_board(...); assert result.id == ...`
  - After: `result = commands.handle_create_board(...); assert isinstance(result, AppOk); assert result.value.id == ...`
- [ ] In `tests/unit/test_kanban_cqrs.py`, update similar direct assertions if present.
- [ ] Run `python -m pytest tests/unit/ -x` — all unit tests pass.
- [ ] Run `python -m pytest tests/integration/ -x` — all integration tests pass.

### Phase 5 — Verify type consistency

- [ ] Run `python -m pytest tests/unit/test_hexagonal_boundaries.py -v` — no regressions.
- [ ] Optionally run mypy: `mypy src/ --strict` — no new type errors introduced.
- [ ] Confirm all seven command handler methods in `KanbanCommandInputPort` return `AppResult[..., ApplicationError]`.
