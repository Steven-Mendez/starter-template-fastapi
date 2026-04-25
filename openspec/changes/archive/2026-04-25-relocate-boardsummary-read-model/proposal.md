# Proposal: Relocate `BoardSummary` Read Model from Domain to Application Layer

**Change ID**: `relocate-boardsummary-read-model`
**Priority**: Medium
**Status**: Proposed

---

## Problem Statement

`src/domain/kanban/models/board_summary.py` defines:

```python
@dataclass(frozen=True, slots=True)
class BoardSummary:
    id: str
    title: str
    created_at: datetime
```

This type is used as the return type of `KanbanCommandRepositoryPort.create_board(...)` and `KanbanQueryRepositoryPort.list_boards()`. It is a **read model projection** — a lightweight DTO for listing boards without loading the full `Board` aggregate with columns and cards.

**Why this does not belong in the domain:**

1. `BoardSummary` has no business behavior. It has no methods, no invariants, and no rules. It is a pure data container shaped by a persistence query (a `SELECT id, title, created_at` operation). Domain models should be entities with behavior or value objects with identity — not query projections.

2. The application layer already maintains an equivalent type: `AppBoardSummary` in `src/application/contracts/kanban.py`:
   ```python
   @dataclass(frozen=True, slots=True)
   class AppBoardSummary:
       id: str
       title: str
       created_at: datetime
   ```
   The two types are structurally identical. The mapping from `BoardSummary → AppBoardSummary` in `src/application/contracts/mappers.py` is pure copy:
   ```python
   def to_app_board_summary(summary: BoardSummary) -> AppBoardSummary:
       return AppBoardSummary(id=summary.id, title=summary.title, created_at=summary.created_at)
   ```
   This mapper does nothing but copy fields. It exists only because the domain `BoardSummary` and application `AppBoardSummary` are separate types.

3. Per `hex-design-guide.md` Section 17: "Sometimes reads do not need rich domain models. A query handler can use a read repository that returns DTOs." DTOs are application-layer concerns. The guide explicitly locates them in the application layer, not the domain.

4. After `relocate-ports-to-application-layer` (Change 1), the repository port (`KanbanQueryRepositoryPort`) will live in `src/application/ports/`. If the port returns `BoardSummary` from the domain, infrastructure adapters will import a domain type through the application port — which is allowed (infrastructure can import domain types) but semantically wrong for a DTO.

**Root cause:** `BoardSummary` was placed in the domain models package early in development, likely because it needed to be accessible to both the repository implementation and the application. The correct solution is to make it an application-layer type returned by the repository port.

---

## Rationale

Per `hex-design-guide.md` Section 34:
> "Application DTO/command/query: use-case input/output"

`BoardSummary` is a use-case output (the result of listing boards). It belongs in `src/application/contracts/` alongside `AppBoard`, `AppCard`, `AppColumn`, and `AppBoardSummary`. Since `AppBoardSummary` already exists and is identical, the simplest fix is to **delete `BoardSummary`** and have the repository port return `AppBoardSummary` directly.

---

## Scope

**In scope:**
- Delete `src/domain/kanban/models/board_summary.py`.
- Remove `BoardSummary` from `src/domain/kanban/models/__init__.py`.
- Change `KanbanQueryRepositoryPort.list_boards()` return type from `list[BoardSummary]` to `list[AppBoardSummary]`.
- Remove `to_app_board_summary` mapper function (becomes a no-op).
- Update `InMemoryKanbanRepository.list_boards()` and `SQLModelKanbanRepository.list_boards()` to construct `AppBoardSummary` directly.
- Update all call sites that reference `BoardSummary` from `src.domain.kanban.models`.

**Out of scope:**
- Changing `AppBoardSummary` field names or types.
- Changing `list_boards()` query behavior or performance.

---

## Affected Modules

| File | Change |
|---|---|
| `src/domain/kanban/models/board_summary.py` | Deleted |
| `src/domain/kanban/models/__init__.py` | Modified — remove `BoardSummary` export |
| `src/application/ports/kanban_query_repository.py` | Modified — `list_boards()` returns `list[AppBoardSummary]` |
| `src/application/ports/kanban_command_repository.py` | Modified — remove `BoardSummary` from return types |
| `src/application/contracts/mappers.py` | Modified — remove `to_app_board_summary` (or keep as alias) |
| `src/infrastructure/persistence/sqlmodel_repository.py` | Modified — `list_boards()` constructs `AppBoardSummary` |
| `src/infrastructure/persistence/in_memory_repository.py` | Modified — `list_boards()` constructs `AppBoardSummary` |
| `tests/support/kanban_builders.py` | Modified — `StoreBuilder.board()` returns `AppBoardSummary` (already uses it) |
| `tests/unit/test_kanban_store.py` | Modified — references `BoardSummary` from domain |
| `tests/unit/test_kanban_repository_contract.py` | Modified — references `BoardSummary` |

---

## Proposed Change

Before (current state):
```
domain/models/ → BoardSummary
application/contracts/ → AppBoardSummary
application/ports/ → list_boards() → list[BoardSummary]  (after Change 1)
application/contracts/mappers/ → to_app_board_summary(BoardSummary) → AppBoardSummary
```

After:
```
domain/models/ → [BoardSummary removed]
application/contracts/ → AppBoardSummary (unchanged)
application/ports/ → list_boards() → list[AppBoardSummary]
application/contracts/mappers/ → [to_app_board_summary removed]
```

Infrastructure adapter `list_boards()` after:
```python
def list_boards(self) -> list[AppBoardSummary]:
    with self._session_scope() as session:
        boards = session.exec(select(BoardTable).order_by("created_at")).all()
    return [
        AppBoardSummary(
            id=board.id,
            title=board.title,
            created_at=_ensure_utc(board.created_at),
        )
        for board in boards
    ]
```

`KanbanQueryHandlers.handle_list_boards()` after — the `to_app_board_summary` mapper call is removed because the repository already returns `AppBoardSummary`:
```python
def handle_list_boards(self, query: ListBoardsQuery) -> list[AppBoardSummary]:
    return self.repository.list_all()    # already list[AppBoardSummary]
```

---

## Acceptance Criteria

1. `src/domain/kanban/models/board_summary.py` does not exist.
2. `BoardSummary` is not exported from `src.domain.kanban.models`.
3. `KanbanQueryRepositoryPort.list_all()` returns `list[AppBoardSummary]`.
4. `to_app_board_summary` mapper function does not exist in `src/application/contracts/mappers.py`.
5. `KanbanQueryHandlers.handle_list_boards()` does not call a mapper for board summaries.
6. `InMemoryKanbanRepository` and `SQLModelKanbanRepository` import `AppBoardSummary` from `src.application.contracts`.
7. All tests pass after the change.

---

## Migration Strategy

1. This change should be applied **after** `relocate-ports-to-application-layer` (ports in application layer before modifying port return types).
2. Change `list_boards()` return type in `KanbanQueryRepositoryPort` → `list[AppBoardSummary]`.
3. Update both repository adapter implementations to import and construct `AppBoardSummary`.
4. Update `handle_list_boards` in `KanbanQueryHandlers` — remove `to_app_board_summary` call.
5. Remove `to_app_board_summary` from `src/application/contracts/mappers.py`.
6. Remove `BoardSummary` from domain `__init__.py` and delete the source file.
7. Search project for `BoardSummary` (from domain) — update any remaining references.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Infrastructure importing from `src.application.contracts` may seem unusual | Infrastructure is allowed to import from application contracts (it implements application ports). This is a valid dependency direction. |
| Removing `to_app_board_summary` may break code that calls it | The only caller is `KanbanQueryHandlers.handle_list_boards`. One call site. |
| Test files that import `BoardSummary` from domain will break | `test_kanban_store.py`, `test_kanban_repository_contract.py` — update after `fix-test-architecture-coupling`. |
